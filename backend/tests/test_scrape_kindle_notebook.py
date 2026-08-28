from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

import app.database as database
from app.models.book import Book
from app.models.highlight import Highlight
from app.services.importer import import_clippings_file
from scripts.scrape_kindle_notebook import (
    _is_note_ui_artifact,
    _kindle_content_hash,
    _parse_location_header,
    import_kindle_highlights,
)

FIXTURE = Path(__file__).parent / "fixtures" / "my_clippings_sample.txt"


def test_parse_location_header_english() -> None:
    assert _parse_location_header("Page 42 · Location 612-618") == (42, 612, 618)
    assert _parse_location_header("Location 100-105") == (None, 100, 105)
    assert _parse_location_header("Page 10") == (10, None, None)


def test_parse_location_header_spanish() -> None:
    # Extra coverage in case another account's notebook page does localize
    # its wording (unconfirmed either way) — cheap to support, costs nothing
    # if unused.
    assert _parse_location_header("Página 42 · Ubicación 612-618") == (42, 612, 618)
    assert _parse_location_header("Página 5 · posición 51-51") == (5, 51, 51)
    assert _parse_location_header("Ubicación 88") == (None, 88, 88)


def test_parse_location_header_matches_real_notebook_format() -> None:
    # Regression test for the actual live bug: verified against a real
    # read.amazon.com/notebook session (24/24 real annotations on one
    # book), the header is "Yellow highlight | Location:\xa029" — English
    # chrome even on this Spanish-content account, and critically a colon
    # directly after "Location" that neither the original regex nor an
    # earlier (wrong-guess) Spanish-locale fix accounted for. All 111 real
    # kindle_notebook highlights in the database had page/location silently
    # left as None before this fix.
    assert _parse_location_header("Yellow highlight | Location:\xa029") == (None, 29, 29)
    assert _parse_location_header("Orange highlight | Location:\xa0184") == (None, 184, 184)


def test_parse_location_header_handles_comma_thousands_separator() -> None:
    # Also verified live: Amazon comma-groups large location numbers
    # ("Location:\xa01,032"). A naive \d+ pattern silently truncated this to
    # 1 instead of 1032 — wrong data, not just missing data.
    assert _parse_location_header("Blue highlight | Location:\xa01,032") == (None, 1032, 1032)
    assert _parse_location_header("Page 1,234 · Location 1,500-1,510") == (1234, 1500, 1510)


def test_is_note_ui_artifact() -> None:
    # Verified live against read.amazon.com/notebook: Amazon's own DOM
    # sometimes populates a dictionary-lookup annotation's note with a bare
    # UI action label instead of user content (confirmed real example:
    # highlight="«experiencias cumbre»", note="Buscar").
    assert _is_note_ui_artifact("Buscar") is True
    assert _is_note_ui_artifact("buscar") is True
    assert _is_note_ui_artifact("  Buscar  ") is True
    assert _is_note_ui_artifact(None) is False
    assert _is_note_ui_artifact("") is False
    assert _is_note_ui_artifact("olvidarse del ego para permitir la existencia.") is False


def test_import_kindle_highlights_merges_with_existing_clippings_book(tmp_path, monkeypatch) -> None:
    """
    Regression test for the live bug: a My Clippings.txt import created a
    book under its "Last, First" author; a Kindle Notebook sync of the same
    book (Amazon's fuller contributor-line author) must land on the same
    book, not split it into a second one with duplicate highlights.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(database, "engine", engine)

    with Session(engine) as session:
        import_clippings_file(FIXTURE, session)
        book = session.exec(select(Book).where(Book.title == "Atomic Habits")).one()
        assert book.author == "James Clear"

    duplicate_text = "You do not rise to the level of your goals. You fall to the level of your systems."
    new_text = "A second highlight scraped straight from the Notebook page."

    records = [
        {
            "book_title": "Atomic Habits",
            "author": "James Clear, Foreword by Some Editor",
            "content": duplicate_text,
            "note": None,
            "highlight_type": "highlight",
            "page": 45,
            "location_start": 689,
            "location_end": 691,
            "date_added": None,
            "source": "kindle_notebook",
            "content_hash": _kindle_content_hash("Atomic Habits", "James Clear", duplicate_text, None, 689, 691),
        },
        {
            "book_title": "Atomic Habits",
            "author": "James Clear, Foreword by Some Editor",
            "content": new_text,
            "note": None,
            "highlight_type": "highlight",
            "page": 46,
            "location_start": 700,
            "location_end": 700,
            "date_added": None,
            "source": "kindle_notebook",
            "content_hash": _kindle_content_hash("Atomic Habits", "James Clear", new_text, None, 700, 700),
        },
    ]

    result = import_kindle_highlights(records)

    assert result["books_created"] == 0, "should reuse the existing book, not create a second one"
    assert result["records_created"] == 1
    assert result["records_skipped"] == 1

    with Session(engine) as session:
        books = session.exec(select(Book).where(Book.title == "Atomic Habits")).all()
        assert len(books) == 1
        highlights = session.exec(select(Highlight).where(Highlight.book_id == books[0].id)).all()
        assert len(highlights) == 2
        contents = {h.content for h in highlights}
        assert new_text in contents


def test_import_kindle_highlights_backfills_page_and_location_on_resync(tmp_path, monkeypatch) -> None:
    """
    Regression test: highlights scraped before the Spanish header-parsing
    fix have page=None/location_start=None even though the highlight text
    itself was captured correctly. Re-syncing with the fixed parser should
    fill in those gaps on the existing row rather than skip it untouched.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(database, "engine", engine)

    text = "negarse al amor destruye el pensamiento."
    stale_hash = _kindle_content_hash("La agonía del Eros", "Han, Byung-Chul", text, None, None, None)
    stale_record = [{
        "book_title": "La agonía del Eros",
        "author": "Han, Byung-Chul",
        "content": text,
        "note": None,
        "highlight_type": "highlight",
        "page": None,
        "location_start": None,
        "location_end": None,
        "date_added": None,
        "source": "kindle_notebook",
        "content_hash": stale_hash,
    }]
    import_kindle_highlights(stale_record)

    with Session(engine) as session:
        stale = session.exec(select(Highlight).where(Highlight.content == text)).one()
        assert stale.page is None
        assert stale.location_start is None

    fresh_hash = _kindle_content_hash("La agonía del Eros", "Han, Byung-Chul", text, None, 75, 75)
    fresh_record = [{
        "book_title": "La agonía del Eros",
        "author": "Han, Byung-Chul",
        "content": text,
        "note": None,
        "highlight_type": "highlight",
        "page": 7,
        "location_start": 75,
        "location_end": 75,
        "date_added": None,
        "source": "kindle_notebook",
        "content_hash": fresh_hash,
    }]
    result = import_kindle_highlights(fresh_record)

    assert result["records_created"] == 0, "should update the existing row, not create a duplicate"
    assert result["records_backfilled"] == 1

    with Session(engine) as session:
        highlights = session.exec(select(Highlight).where(Highlight.content == text)).all()
        assert len(highlights) == 1, "must not have duplicated the highlight"
        assert highlights[0].page == 7
        assert highlights[0].location_start == 75
        assert highlights[0].location_end == 75


def test_import_kindle_highlights_backfills_page_when_hash_is_unchanged(tmp_path, monkeypatch) -> None:
    """
    Regression test for a real gap found by running the actual scraper
    end-to-end: _kindle_content_hash doesn't include `page`, only location.
    A book with page-only headers and no location (a fixed-layout edition —
    confirmed live on "Hyperfocus") hashes identically whether or not page
    was captured, so a resync matches it via the exact-hash path (Dedup 1),
    not the content-text path (Dedup 2). Backfill used to only be wired
    into Dedup 2, so 57/57 highlights on that real book stayed page=None
    even after a resync that correctly scraped their page numbers.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(database, "engine", engine)

    text = "disconnecting is one of the most powerful ways to spark new ideas."
    # location is None in both scrapes, so the hash is identical either way.
    same_hash = _kindle_content_hash("Hyperfocus", "Chris Bailey", text, None, None, None)

    stale_record = [{
        "book_title": "Hyperfocus", "author": "Chris Bailey", "content": text, "note": None,
        "highlight_type": "highlight", "page": None, "location_start": None, "location_end": None,
        "date_added": None, "source": "kindle_notebook", "content_hash": same_hash,
    }]
    import_kindle_highlights(stale_record)

    fresh_record = [{
        "book_title": "Hyperfocus", "author": "Chris Bailey", "content": text, "note": None,
        "highlight_type": "highlight", "page": 3, "location_start": None, "location_end": None,
        "date_added": None, "source": "kindle_notebook", "content_hash": same_hash,
    }]
    result = import_kindle_highlights(fresh_record)

    assert result["records_created"] == 0
    assert result["records_backfilled"] == 1, "page should be backfilled even when matched via the exact-hash path"

    with Session(engine) as session:
        highlights = session.exec(select(Highlight).where(Highlight.content == text)).all()
        assert len(highlights) == 1
        assert highlights[0].page == 3
