from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session, func, select

from app.database import engine, init_db
from app.models.book import Book
from app.models.highlight import Highlight
from app.models.import_log import ImportLog
from app.services.book_identity import authors_compatible, get_or_create_book, normalize_identity
from app.services.clippings_parser import ParsedClipping, parse_file


@dataclass(frozen=True)
class ImportSummary:
    source: str
    file_name: str | None
    records_seen: int
    records_created: int
    records_skipped: int
    records_failed: int
    books_created: int
    import_log_id: str


@dataclass(frozen=True)
class MergeSummary:
    books_merged: int
    highlights_moved: int
    duplicate_highlights_removed: int


def import_clippings_file(path: str | Path, session: Session) -> ImportSummary:
    file_path = Path(path)
    parse_result = parse_file(file_path)
    return import_records(
        parse_result.records,
        session,
        source="my_clippings",
        file_name=file_path.name,
        parse_skipped=parse_result.skipped,
        parse_errors=parse_result.errors,
    )


def import_records(
    records: list[ParsedClipping],
    session: Session,
    source: str = "my_clippings",
    file_name: str | None = None,
    parse_skipped: int = 0,
    parse_errors: list[str] | None = None,
) -> ImportSummary:
    now = datetime.now(timezone.utc)
    books_created = 0
    records_created = 0
    records_skipped = parse_skipped
    records_failed = 0
    errors = list(parse_errors or [])

    for record in records:
        try:
            book, was_created = get_or_create_book(session, record.book_title, record.author, now)
            if was_created:
                books_created += 1

            exists = session.exec(
                select(Highlight).where(
                    Highlight.book_id == book.id,
                    Highlight.content_hash == record.content_hash,
                )
            ).first()
            if exists:
                records_skipped += 1
                continue

            # Cross-source duplicate: the same highlight text can arrive with
            # a different content_hash if it came from another source (the
            # Kindle Notebook scraper's hash includes a source prefix, so
            # identical text never produces a matching hash there). Fall
            # back to a normalized-content comparison within this book.
            record_text = normalize_identity(record.content or record.note or "")
            if record_text:
                book_highlights = session.exec(select(Highlight).where(Highlight.book_id == book.id)).all()
                if any(normalize_identity(h.content or h.note or "") == record_text for h in book_highlights):
                    records_skipped += 1
                    continue

            session.add(
                Highlight(
                    book_id=book.id,
                    content=record.content,
                    note=record.note,
                    highlight_type=record.highlight_type,
                    page=record.page,
                    location_start=record.location_start,
                    location_end=record.location_end,
                    date_added=_parse_iso_datetime(record.date_added),
                    source=record.source,
                    content_hash=record.content_hash,
                    created_at=now,
                    updated_at=now,
                )
            )

            book.total_highlights += 1
            book.last_imported_at = now
            book.updated_at = now
            session.add(book)
            records_created += 1
        except Exception as exc:  # pragma: no cover - defensive log path
            records_failed += 1
            errors.append(f"{record.book_title}: {exc}")

    log = ImportLog(
        source=source,
        file_name=file_name,
        records_seen=len(records) + parse_skipped,
        records_created=records_created,
        records_skipped=records_skipped,
        records_failed=records_failed,
        error_summary="\n".join(errors[:20]) if errors else None,
        created_at=now,
    )
    session.add(log)
    session.commit()
    session.refresh(log)

    # Self-heal: catch books split across sources (e.g. My Clippings.txt's
    # "Last, First" author vs. the Kindle Notebook scraper's full contributor
    # line) so duplicates never accumulate silently between imports.
    merge_duplicate_books(session)

    return ImportSummary(
        source=source,
        file_name=file_name,
        records_seen=len(records) + parse_skipped,
        records_created=records_created,
        records_skipped=records_skipped,
        records_failed=records_failed,
        books_created=books_created,
        import_log_id=str(log.id),
    )


def merge_duplicate_books(session: Session) -> MergeSummary:
    books = session.exec(select(Book).order_by(Book.created_at)).all()
    canonical_by_key: dict[tuple[str, str], Book] = {}
    books_merged = 0
    highlights_moved = 0
    duplicate_highlights_removed = 0

    for book in books:
        # Group by title first. We merge if titles match and authors are compatible
        # (not necessarily identical — see authors_compatible).
        title_key = normalize_identity(book.title)

        # Find if we already have a canonical book for this title
        canonical = None
        for (c_title, c_author), c_book in canonical_by_key.items():
            if c_title == title_key and authors_compatible(c_book.author, book.author):
                canonical = c_book
                # Update canonical author if missing
                if not canonical.author and book.author:
                    canonical.author = book.author
                    # Update the key with the new author
                    del canonical_by_key[(c_title, c_author)]
                    canonical_by_key[(c_title, normalize_identity(book.author))] = canonical
                break

        if canonical is None:
            # First time seeing this title/author combo
            canonical_by_key[(title_key, normalize_identity(book.author or ""))] = book
            continue

        # Highlight-level dedup can't rely on content_hash alone: the Kindle
        # Notebook scraper and the My Clippings.txt parser hash the same text
        # differently (the scraper's hash includes a source prefix), so an
        # identical highlight pulled from both sources never has a matching
        # hash. Fall back to normalized-content comparison, which is what
        # actually catches the duplicate.
        canonical_highlights = session.exec(select(Highlight).where(Highlight.book_id == canonical.id)).all()
        canonical_hashes = {h.content_hash for h in canonical_highlights}
        canonical_content = {normalize_identity(h.content or h.note or "") for h in canonical_highlights}

        highlights = session.exec(select(Highlight).where(Highlight.book_id == book.id)).all()
        for highlight in highlights:
            highlight_content = normalize_identity(highlight.content or highlight.note or "")
            is_duplicate = highlight.content_hash in canonical_hashes or highlight_content in canonical_content
            if is_duplicate:
                session.delete(highlight)
                duplicate_highlights_removed += 1
            else:
                highlight.book_id = canonical.id
                session.add(highlight)
                highlights_moved += 1
                canonical_hashes.add(highlight.content_hash)
                canonical_content.add(highlight_content)

        session.delete(book)
        books_merged += 1

    for book in canonical_by_key.values():
        count = session.exec(select(func.count(Highlight.id)).where(Highlight.book_id == book.id)).one()
        book.total_highlights = count
        book.updated_at = datetime.now(timezone.utc)
        session.add(book)

    session.commit()
    return MergeSummary(
        books_merged=books_merged,
        highlights_moved=highlights_moved,
        duplicate_highlights_removed=duplicate_highlights_removed,
    )


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Kindle My Clippings.txt into the Synapse SQLite database.")
    parser.add_argument("--input", required=True, help="Path to My Clippings.txt")
    args = parser.parse_args()

    init_db()
    with Session(engine) as session:
        summary = import_clippings_file(args.input, session)

    print(
        " ".join(
            [
                f"seen={summary.records_seen}",
                f"created={summary.records_created}",
                f"skipped={summary.records_skipped}",
                f"failed={summary.records_failed}",
                f"books_created={summary.books_created}",
                f"import_log_id={summary.import_log_id}",
            ]
        )
    )


if __name__ == "__main__":
    main()
