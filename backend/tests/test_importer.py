from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

from app.models.book import Book
from app.models.highlight import Highlight
from app.models.import_log import ImportLog
from app.services.importer import import_clippings_file, import_records, merge_duplicate_books


def test_import_clippings_is_idempotent(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    fixture = Path(__file__).parent / "fixtures" / "my_clippings_sample.txt"

    with Session(engine) as session:
        first = import_clippings_file(fixture, session)
        second = import_clippings_file(fixture, session)

        books = session.exec(select(Book)).all()
        highlights = session.exec(select(Highlight)).all()
        logs = session.exec(select(ImportLog)).all()

    assert first.records_seen == 4
    assert first.records_created == 4
    assert first.records_skipped == 0
    assert first.books_created == 4

    assert second.records_seen == 4
    assert second.records_created == 0
    assert second.records_skipped == 4
    assert second.books_created == 0

    assert len(books) == 4
    assert len(highlights) == 4
    assert len(logs) == 2


def test_import_merges_book_identity_case_and_spacing(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    from app.services.clippings_parser import ParsedClipping

    first = ParsedClipping(
        book_title="Atomic Habits",
        author="James Clear",
        content="A",
        note=None,
        highlight_type="highlight",
        page=None,
        location_start=1,
        location_end=1,
        date_added=None,
        source="my_clippings",
        content_hash="hash-a",
    )
    second = ParsedClipping(
        book_title=" atomic   habits ",
        author="james clear",
        content="B",
        note=None,
        highlight_type="highlight",
        page=None,
        location_start=2,
        location_end=2,
        date_added=None,
        source="my_clippings",
        content_hash="hash-b",
    )

    with Session(engine) as session:
        summary = import_records([first, second], session)
        books = session.exec(select(Book)).all()
        highlights = session.exec(select(Highlight)).all()

    assert summary.records_created == 2
    assert summary.books_created == 1
    assert len(books) == 1
    assert books[0].total_highlights == 2
    assert len(highlights) == 2


def test_merge_duplicate_books_repairs_existing_bom_split(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        clean = Book(title="La agonía del Eros", author="Han, Byung-Chul", total_highlights=1)
        bom = Book(title="\ufeffLa agonía del Eros", author="Han, Byung-Chul", total_highlights=1)
        session.add(clean)
        session.add(bom)
        session.commit()
        session.refresh(clean)
        session.refresh(bom)
        session.add(Highlight(book_id=clean.id, content="A", content_hash="hash-a"))
        session.add(Highlight(book_id=bom.id, content="B", content_hash="hash-b"))
        session.commit()

        summary = merge_duplicate_books(session)
        books = session.exec(select(Book)).all()
        highlights = session.exec(select(Highlight)).all()

    assert summary.books_merged == 1
    assert summary.highlights_moved == 1
    assert len(books) == 1
    assert books[0].total_highlights == 2
    assert len(highlights) == 2
