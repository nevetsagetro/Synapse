"""
scrape_kindle_notebook.py
─────────────────────────
Extracts all highlights from https://read.amazon.com/notebook using
Playwright and imports them into the Synapse SQLite database.

This scraper is completely independent from the My Clippings.txt file
importer. Highlights from this source are tagged source="kindle_notebook"
and deduplicated separately — the same highlight text may coexist in both
sources if imported via both methods.

Authentication
--------------
The first run opens a visible Chromium window and waits up to 5 minutes
for you to complete your Amazon login (including MFA / OTP).
After a successful login the session is saved to:
    ~/.synapse/kindle_session.json

Subsequent runs reuse the saved session and run headlessly by default.
Pass --headed to always open the browser window.

Usage
─────
From the backend/ directory (with .venv active):

    # First run – manual login required:
    python -m scripts.scrape_kindle_notebook

    # Later runs – fully automatic:
    python -m scripts.scrape_kindle_notebook

    # Always open browser:
    python -m scripts.scrape_kindle_notebook --headed

    # Only scrape, don't import (prints JSON):
    python -m scripts.scrape_kindle_notebook --dry-run

    # Reset saved session (force re-login):
    python -m scripts.scrape_kindle_notebook --reset-session
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

NOTEBOOK_URL = "https://read.amazon.com/notebook"
SESSION_FILE = Path.home() / ".synapse" / "kindle_session.json"
LOGIN_WAIT_MS = 5 * 60 * 1_000  # 5 minutes

SOURCE = "kindle_notebook"

# ── CSS selectors ──────────────────────────────────────────────────────────
#
# The sidebar book list has alternating .kp-notebook-searchable spans:
#   span[0] = title of book 1
#   span[1] = "By: Author" of book 1
#   span[2] = title of book 2
#   span[3] = "By: Author" of book 2
#   ...
#
# We collect all spans and iterate in steps of 2 to pair title + author.
# Clicking the title span loads that book's annotations in the right pane.
#
_SEL_LIBRARY         = "#kp-notebook-library"
_SEL_BOOK_SPANS      = "#kp-notebook-library .kp-notebook-searchable"
_SEL_ANNOT_CONTAINER  = ".a-row.a-spacing-base"
_SEL_HIGHLIGHT_TEXT   = "#highlight"
_SEL_NOTE_TEXT        = "#note"
_SEL_ANNOT_HEADER     = "#annotationHighlightHeader"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _kindle_content_hash(
    book_title: str,
    author: Optional[str],
    content: str,
    note: Optional[str],
    location_start: Optional[int],
    location_end: Optional[int],
) -> str:
    """Stable hash that identifies a unique highlight within the kindle_notebook source."""
    def norm(v: str) -> str:
        return re.sub(r"\s+", " ", v.strip().casefold())

    parts = [
        SOURCE,
        norm(book_title),
        norm(author or ""),
        norm(content),
        norm(note or ""),
        str(location_start or ""),
        str(location_end or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _parse_location_header(header_text: str) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """
    Parse the annotation header string produced by Amazon, e.g.:
        "Page 42 · Location 612-618"
        "Location 100-105"
        "Page 10"

    Amazon localizes this header to the account's language, and the
    read.amazon.com/notebook page's own wording doesn't necessarily match
    the device-exported My Clippings.txt wording (e.g. it may use
    "Ubicación" where the file export uses "posición") — this used to only
    recognize English "Page"/"Location" and silently returned (None, None,
    None) for every single highlight on any non-English account.

    Returns (page, location_start, location_end).
    """
    page: Optional[int] = None
    loc_start: Optional[int] = None
    loc_end: Optional[int] = None

    page_match = re.search(r"(?:[Pp]age|[Pp]ágina)\s+(\d+)", header_text)
    if page_match:
        page = int(page_match.group(1))

    loc_match = re.search(r"(?:[Ll]ocation|[Pp]osición|[Uu]bicación)\s+(\d+)(?:\s*-\s*(\d+))?", header_text)
    if loc_match:
        loc_start = int(loc_match.group(1))
        loc_end = int(loc_match.group(2)) if loc_match.group(2) else loc_start

    return page, loc_start, loc_end


def _parse_author(raw: str) -> Optional[str]:
    """Strip 'By: ' prefix that Amazon prepends to author lines."""
    cleaned = re.sub(r"^[Bb]y:\s*", "", raw.strip()).strip()
    return cleaned or None


# ---------------------------------------------------------------------------
# Core scraping logic
# ---------------------------------------------------------------------------


def _ensure_session_dir() -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)


def scrape_highlights(*, headed: bool = False, reset_session: bool = False) -> list[dict]:
    """
    Open the Kindle Notebook page and scrape all highlights.

    Returns a list of raw record dicts (matching the ParsedClipping field layout)
    tagged with source="kindle_notebook".
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        print(
            "ERROR: playwright is not installed.\n"
            "Run: pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        sys.exit(1)

    _ensure_session_dir()

    has_session = SESSION_FILE.exists() and not reset_session
    if reset_session and SESSION_FILE.exists():
        SESSION_FILE.unlink()
        print("🗑️  Deleted saved session. You will need to log in again.")
        has_session = False

    results: list[dict] = []

    with sync_playwright() as pw:
        # First attempt: headless only if we have a saved session
        headless = has_session and not headed
        browser = pw.chromium.launch(headless=headless)
        ctx_kwargs: dict = {
            "user_agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "viewport": {"width": 1280, "height": 900},
        }
        if has_session:
            ctx_kwargs["storage_state"] = str(SESSION_FILE)

        context = browser.new_context(**ctx_kwargs)
        page = context.new_page()

        # ── Navigate ────────────────────────────────────────────────────────
        print(f"🌐  Navigating to {NOTEBOOK_URL} …")
        page.goto(NOTEBOOK_URL, wait_until="domcontentloaded", timeout=60_000)

        # ── Login check ─────────────────────────────────────────────────────
        needs_login = not has_session or "signin" in page.url or "ap/signin" in page.url
        if needs_login:
            # If we went headless but got redirected to login, restart headed
            if headless:
                browser.close()
                browser = pw.chromium.launch(headless=False)
                clean_ctx = {k: v for k, v in ctx_kwargs.items() if k != "storage_state"}
                context = browser.new_context(**clean_ctx)
                page = context.new_page()
                page.goto(NOTEBOOK_URL, wait_until="domcontentloaded", timeout=60_000)

            print(
                "\n🔐  Login required!\n"
                "    A browser window has opened. Please sign in to Amazon.\n"
                "    Waiting up to 5 minutes …\n"
            )
            try:
                page.wait_for_url(
                    lambda url: "read.amazon.com/notebook" in url,
                    timeout=LOGIN_WAIT_MS,
                )
            except PWTimeout:
                print("❌  Login timed out. Please try again.", file=sys.stderr)
                browser.close()
                sys.exit(1)

            # Save session for next time
            context.storage_state(path=str(SESSION_FILE))
            print(f"✅  Session saved to {SESSION_FILE}\n")

        # ── Wait for book library to render ──────────────────────────────────
        print("⏳  Waiting for book library to load …")
        library_found = False
        try:
            page.wait_for_selector(_SEL_LIBRARY, timeout=30_000)
            page.wait_for_selector(_SEL_BOOK_SPANS, timeout=15_000)
            library_found = True
        except Exception:
            pass

        if not library_found:
            # Headless session may be stale — retry headed so user can re-login
            if headless:
                print("⚠️  Session appears stale. Restarting in headed mode for re-login …")
                browser.close()
                browser = pw.chromium.launch(headless=False)
                clean_ctx = {k: v for k, v in ctx_kwargs.items() if k != "storage_state"}
                context = browser.new_context(**clean_ctx)
                page = context.new_page()
                page.goto(NOTEBOOK_URL, wait_until="domcontentloaded", timeout=60_000)
                print(
                    "\n🔐  Please sign in to Amazon in the browser window.\n"
                    "    Waiting up to 5 minutes …\n"
                )
                try:
                    from playwright.sync_api import TimeoutError as PWTimeout
                    page.wait_for_url(
                        lambda url: "read.amazon.com/notebook" in url,
                        timeout=LOGIN_WAIT_MS,
                    )
                except PWTimeout:
                    print("❌  Login timed out. Please try again.", file=sys.stderr)
                    browser.close()
                    sys.exit(1)
                context.storage_state(path=str(SESSION_FILE))
                print(f"✅  Session refreshed and saved to {SESSION_FILE}\n")
                try:
                    page.wait_for_selector(_SEL_LIBRARY, timeout=30_000)
                    page.wait_for_selector(_SEL_BOOK_SPANS, timeout=15_000)
                except Exception:
                    print(
                        "❌  Could not find the book library after re-login.\n"
                        "    Make sure you have Kindle highlights at read.amazon.com/notebook",
                        file=sys.stderr,
                    )
                    browser.close()
                    sys.exit(1)
            else:
                print(
                    "❌  Could not find the book library.\n"
                    "    Try: python -m scripts.scrape_kindle_notebook --reset-session",
                    file=sys.stderr,
                )
                browser.close()
                sys.exit(1)

        # ── Scroll library to load all books (infinite scroll) ───────────────
        print("⏳  Scrolling to load all books in library …")
        previous_span_count = 0
        while True:
            # Scroll the library container to the bottom
            page.evaluate("""
                const el = document.querySelector('#kp-notebook-library');
                if (el) el.scrollTop = el.scrollHeight;
            """)
            page.wait_for_timeout(1500)  # Wait for new books to render
            
            current_span_count = len(page.query_selector_all(_SEL_BOOK_SPANS))
            if current_span_count == previous_span_count:
                break  # Reached the end
            previous_span_count = current_span_count

        # ── Collect all book spans and pair them (title, author) ─────────────
        # The sidebar emits alternating spans: title, By: author, title, By: author …
        all_spans = page.query_selector_all(_SEL_BOOK_SPANS)
        book_items: list[tuple[str, Optional[str], object]] = []
        for i in range(0, len(all_spans), 2):
            title_el   = all_spans[i]
            author_el  = all_spans[i + 1] if i + 1 < len(all_spans) else None
            book_title = (title_el.inner_text() or "").strip()
            author_raw = (author_el.inner_text() or "").strip() if author_el else ""
            book_items.append((book_title, _parse_author(author_raw), title_el))

        total_books = len(book_items)
        print(f"📚  Found {total_books} book(s) in your library.\n")

        for book_idx, (book_title, author, click_el) in enumerate(book_items, start=1):
            print(f"  [{book_idx}/{total_books}] {book_title}" + (f" — {author}" if author else ""))

            # Everything for this book — click, page load, and extraction — is
            # guarded together. A scrape can run for many minutes across a
            # whole library; without this, one bad annotation on book 90 of
            # 100 would raise out of the entire function and silently
            # discard every highlight already gathered from books 1-89,
            # since results are only written to the database after this
            # whole loop returns (see import_kindle_highlights below).
            try:
                click_el.click()
                page.wait_for_timeout(500) # Wait for JS event loop to start the fetch
                page.wait_for_load_state("networkidle", timeout=15_000)
                page.wait_for_timeout(1000) # Wait for DOM to render the new annotations

                # ── Scrape annotations ───────────────────────────────────
                annotation_containers = page.query_selector_all(_SEL_ANNOT_CONTAINER)
                highlight_count = 0

                for container in annotation_containers:
                    highlight_el = container.query_selector(_SEL_HIGHLIGHT_TEXT)
                    note_el      = container.query_selector(_SEL_NOTE_TEXT)
                    header_el    = container.query_selector(_SEL_ANNOT_HEADER)

                    highlight_text = (highlight_el.inner_text() if highlight_el else "").strip()
                    note_text      = (note_el.inner_text()      if note_el      else "").strip() or None
                    header_text    = (header_el.inner_text()    if header_el    else "").strip()

                    if not highlight_text:
                        continue

                    page_num, loc_start, loc_end = _parse_location_header(header_text)
                    ch = _kindle_content_hash(book_title, author, highlight_text, note_text, loc_start, loc_end)

                    results.append({
                        "book_title":     book_title,
                        "author":         author,
                        "content":        highlight_text,
                        "note":           note_text,
                        "highlight_type": "highlight",
                        "page":           page_num,
                        "location_start": loc_start,
                        "location_end":   loc_end,
                        "date_added":     None,
                        "source":         SOURCE,
                        "content_hash":   ch,
                    })
                    highlight_count += 1

                print(f"    ✔  {highlight_count} highlight(s)")
            except Exception as e:
                print(f"    ⚠️  Could not scrape this book, skipping it: {e}")
                continue

        browser.close()

    print(f"\n📋  Total highlights scraped: {len(results)}")
    return results


# ---------------------------------------------------------------------------
# Kindle-specific import (separate from the My Clippings importer)
# ---------------------------------------------------------------------------


def import_kindle_highlights(raw_records: list[dict]) -> dict:
    """
    Import scraped Kindle Notebook highlights into Synapse.

    This is intentionally separate from import_records() used by
    My Clippings.txt ingestion.  Deduplication uses source + content_hash
    so highlights from this source never collide with file-imported ones.
    """
    from app.database import engine, init_db
    from app.models.highlight import Highlight
    from app.models.import_log import ImportLog
    from app.services.book_identity import get_or_create_book, normalize_identity
    from app.services.importer import merge_duplicate_books
    from sqlmodel import Session, select

    if not raw_records:
        return {
            "source": SOURCE,
            "records_seen": 0,
            "records_created": 0,
            "records_skipped": 0,
            "records_failed": 0,
            "records_backfilled": 0,
            "books_created": 0,
            "import_log_id": None,
        }

    init_db()
    now = datetime.now(timezone.utc)
    books_created = 0
    records_created = 0
    records_skipped = 0
    records_failed = 0
    records_backfilled = 0
    errors: list[str] = []

    with Session(engine) as session:
        for record in raw_records:
            try:
                book, was_created = get_or_create_book(
                    session, record["book_title"], record["author"], now
                )
                if was_created:
                    books_created += 1

                # ── Dedup 1: exact kindle_notebook hash (same source re-run) ──
                exists_same_source = session.exec(
                    select(Highlight).where(
                        Highlight.book_id      == book.id,
                        Highlight.source       == SOURCE,
                        Highlight.content_hash == record["content_hash"],
                    )
                ).first()
                if exists_same_source:
                    records_skipped += 1
                    continue

                # ── Dedup 2: cross-source — skip if same text already exists ──
                # (the my_clippings version is richer: it has page/location/date)
                norm_incoming = normalize_identity(record["content"])
                all_book_highlights = session.exec(
                    select(Highlight).where(Highlight.book_id == book.id)
                ).all()
                matching_highlight = next(
                    (h for h in all_book_highlights if normalize_identity(h.content or "") == norm_incoming),
                    None,
                )
                if matching_highlight is not None:
                    # Backfill metadata an earlier scrape couldn't capture
                    # (e.g. page/location, before the header-parsing regex
                    # recognized Spanish headers) instead of silently
                    # discarding a richer re-scrape of the same highlight.
                    # Only fills gaps — never overwrites data already there.
                    backfilled = False
                    if matching_highlight.page is None and record["page"] is not None:
                        matching_highlight.page = record["page"]
                        backfilled = True
                    if matching_highlight.location_start is None and record["location_start"] is not None:
                        matching_highlight.location_start = record["location_start"]
                        matching_highlight.location_end = record["location_end"]
                        backfilled = True
                    if not matching_highlight.note and record["note"]:
                        matching_highlight.note = record["note"]
                        backfilled = True
                    if backfilled:
                        matching_highlight.updated_at = now
                        session.add(matching_highlight)
                        records_backfilled += 1
                    records_skipped += 1
                    continue

                session.add(Highlight(
                    book_id        = book.id,
                    content        = record["content"],
                    note           = record["note"],
                    highlight_type = record["highlight_type"],
                    page           = record["page"],
                    location_start = record["location_start"],
                    location_end   = record["location_end"],
                    date_added     = None,
                    source         = SOURCE,
                    content_hash   = record["content_hash"],
                    created_at     = now,
                    updated_at     = now,
                ))
                book.total_highlights += 1
                book.last_imported_at  = now
                book.updated_at        = now
                session.add(book)
                records_created += 1

            except Exception as exc:
                records_failed += 1
                errors.append(f"{record.get('book_title', '?')}: {exc}")

        log = ImportLog(
            source          = SOURCE,
            file_name       = None,
            records_seen    = len(raw_records),
            records_created = records_created,
            records_skipped = records_skipped,
            records_failed  = records_failed,
            error_summary   = "\n".join(errors[:20]) if errors else None,
            created_at      = now,
        )
        session.add(log)
        session.commit()
        session.refresh(log)
        log_id = str(log.id)

        # Self-heal: catch books split across sources (e.g. an author string
        # that differs between My Clippings.txt and this scraper) so
        # duplicates never accumulate silently between imports. This commits
        # again internally, which is why log_id was captured above rather
        # than read from `log` after this point — commit() expires ORM
        # objects, and by the time we return, the session is closed.
        merge_duplicate_books(session)

    return {
        "source":             SOURCE,
        "records_seen":       len(raw_records),
        "records_created":    records_created,
        "records_skipped":    records_skipped,
        "records_failed":     records_failed,
        "records_backfilled": records_backfilled,
        "books_created":      books_created,
        "import_log_id":      log_id,
    }


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape highlights from read.amazon.com/notebook and import them into Synapse.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Always open a visible browser (default: headless after first login)",
    )
    parser.add_argument(
        "--reset-session",
        action="store_true",
        help="Delete saved session and force re-login",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape only – print JSON, do not write to the database",
    )
    parser.add_argument(
        "--session-file",
        default=None,
        help="Path to session file (default: ~/.synapse/kindle_session.json)",
    )
    args = parser.parse_args()

    global SESSION_FILE  # noqa: PLW0603
    if args.session_file:
        SESSION_FILE = Path(args.session_file)

    records = scrape_highlights(headed=args.headed, reset_session=args.reset_session)

    if args.dry_run:
        print(json.dumps(records, indent=2, ensure_ascii=False))
        return

    if not records:
        print("No highlights found – nothing to import.")
        return

    print("\n⬆️  Importing into Synapse database …")
    summary = import_kindle_highlights(records)
    print(
        "\n✅  Import complete:\n"
        f"   source={summary['source']}\n"
        f"   seen={summary['records_seen']}\n"
        f"   created={summary['records_created']}\n"
        f"   skipped={summary['records_skipped']}\n"
        f"   failed={summary['records_failed']}\n"
        f"   books_created={summary['books_created']}\n"
        f"   import_log_id={summary['import_log_id']}"
    )


if __name__ == "__main__":
    main()
