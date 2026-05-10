from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session, func, select

from app.database import engine, init_db
from app.models.book import Book
from app.models.highlight import Highlight
from app.models.import_log import ImportLog
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
            book, was_created = _get_or_create_book(session, record, now)
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


def _get_or_create_book(session: Session, record: ParsedClipping, now: datetime) -> tuple[Book, bool]:
    normalized_title = _normalize_identity(record.book_title)
    normalized_author = _normalize_identity(record.author or "")

    books = session.exec(select(Book)).all()
    for book in books:
        if _normalize_identity(book.title) == normalized_title and _normalize_identity(book.author or "") == normalized_author:
            return book, False

    book = Book(
        title=record.book_title,
        author=record.author,
        first_imported_at=now,
        last_imported_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(book)
    session.flush()
    session.refresh(book)
    return book, True


def merge_duplicate_books(session: Session) -> MergeSummary:
    books = session.exec(select(Book).order_by(Book.created_at)).all()
    canonical_by_key: dict[tuple[str, str], Book] = {}
    books_merged = 0
    highlights_moved = 0
    duplicate_highlights_removed = 0

    for book in books:
        key = (_normalize_identity(book.title), _normalize_identity(book.author or ""))
        canonical = canonical_by_key.get(key)
        if canonical is None:
            canonical_by_key[key] = book
            continue

        highlights = session.exec(select(Highlight).where(Highlight.book_id == book.id)).all()
        for highlight in highlights:
            existing = session.exec(
                select(Highlight).where(
                    Highlight.book_id == canonical.id,
                    Highlight.content_hash == highlight.content_hash,
                )
            ).first()
            if existing:
                session.delete(highlight)
                duplicate_highlights_removed += 1
            else:
                highlight.book_id = canonical.id
                session.add(highlight)
                highlights_moved += 1

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


def _normalize_identity(value: str) -> str:
    cleaned = re.sub(r"[\ufeff\u200b\u200c\u200d]", "", value)
    return re.sub(r"\s+", " ", cleaned.strip().casefold())


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
