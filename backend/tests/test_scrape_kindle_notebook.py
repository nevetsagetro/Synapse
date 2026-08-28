from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

import app.database as database
from app.models.book import Book
from app.models.highlight import Highlight
from app.services.importer import import_clippings_file
from scripts.scrape_kindle_notebook import _kindle_content_hash, _parse_location_header, import_kindle_highlights

FIXTURE = Path(__file__).parent / "fixtures" / "my_clippings_sample.txt"


def test_parse_location_header_english() -> None:
    assert _parse_location_header("Page 42 · Location 612-618") == (42, 612, 618)
    assert _parse_location_header("Location 100-105") == (None, 100, 105)
    assert _parse_location_header("Page 10") == (10, None, None)


def test_parse_location_header_spanish() -> None:
    # Regression test: Amazon localizes the notebook page's annotation
    # header to the account's language. Every one of this project's real
    # kindle_notebook-sourced highlights (a Spanish-language account) had
    # page and location silently left as None before this was fixed to
    # recognize "Página"/"Ubicación"/"posición" too.
    assert _parse_location_header("Página 42 · Ubicación 612-618") == (42, 612, 618)
    assert _parse_location_header("Página 5 · posición 51-51") == (5, 51, 51)
    assert _parse_location_header("Ubicación 88") == (None, 88, 88)


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
