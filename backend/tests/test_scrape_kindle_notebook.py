from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

import app.database as database
from app.models.book import Book
from app.models.highlight import Highlight
from app.services.importer import import_clippings_file
from scripts.scrape_kindle_notebook import _kindle_content_hash, import_kindle_highlights

FIXTURE = Path(__file__).parent / "fixtures" / "my_clippings_sample.txt"


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
