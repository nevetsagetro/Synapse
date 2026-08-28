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


def test_import_records_merges_books_across_differing_author_formats(tmp_path: Path) -> None:
    # Regression test for the live bug: My Clippings.txt import created
    # "La agonía del Eros" / "Han, Byung-Chul" (13 highlights); a later
    # Kindle Notebook sync created a second "La agonía del Eros" book under
    # the full contributor string, and none of its highlights were caught
    # as duplicates because the cross-source dedup was scoped to book_id.
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    from app.services.clippings_parser import ParsedClipping

    from_clippings = ParsedClipping(
        book_title="La agonía del Eros (Spanish Edition)",
        author="Han, Byung-Chul",
        content="La experiencia amorosa es toda ella un entramado de impotencia,",
        note=None,
        highlight_type="highlight",
        page=5,
        location_start=51,
        location_end=51,
        date_added=None,
        source="my_clippings",
        content_hash="clippings-hash-1",
    )
    # Same highlight text, but hashed the way the Kindle Notebook scraper
    # hashes it (source-prefixed), so content_hash never matches across
    # sources even for identical text — the dedup must fall back to content.
    from_notebook_duplicate = ParsedClipping(
        book_title="La agonía del Eros (Spanish Edition)",
        author="Byung-Chul Han, Antoni Martínez Riu, Raúl Gabás, Alain Badiou, and Ferran Fernández",
        content="La experiencia amorosa es toda ella un entramado de impotencia,",
        note=None,
        highlight_type="highlight",
        page=5,
        location_start=51,
        location_end=51,
        date_added=None,
        source="kindle_notebook",
        content_hash="kindle_notebook|different-hash-scheme",
    )
    from_notebook_new = ParsedClipping(
        book_title="La agonía del Eros (Spanish Edition)",
        author="Byung-Chul Han, Antoni Martínez Riu, Raúl Gabás, Alain Badiou, and Ferran Fernández",
        content="ya que el amor verdadero asume que es necesario no ser ya nada",
        note=None,
        highlight_type="highlight",
        page=6,
        location_start=54,
        location_end=55,
        date_added=None,
        source="kindle_notebook",
        content_hash="kindle_notebook|another-different-hash",
    )

    with Session(engine) as session:
        import_records([from_clippings], session, source="my_clippings")
        import_records([from_notebook_duplicate, from_notebook_new], session, source="kindle_notebook")

        books = session.exec(select(Book)).all()
        highlights = session.exec(select(Highlight)).all()

    assert len(books) == 1, "the two author formats should resolve to one book"
    assert books[0].total_highlights == 2
    assert len(highlights) == 2, "the duplicate highlight (different hash, same text) should be removed"
    contents = {h.content for h in highlights}
    assert "La experiencia amorosa es toda ella un entramado de impotencia," in contents
    assert "ya que el amor verdadero asume que es necesario no ser ya nada" in contents


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
