from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app
from app.services.importer import import_clippings_file

FIXTURE = Path(__file__).parent / "fixtures" / "my_clippings_sample.txt"


def test_books_sort_options(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        import_clippings_file(FIXTURE, session)

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    client = TestClient(app)

    try:
        by_title = client.get("/api/books", params={"sort": "title"}).json()
        titles = [b["title"] for b in by_title]
        assert titles == sorted(titles, key=str.casefold)

        by_recent = client.get("/api/books", params={"sort": "recent"}).json()
        assert len(by_recent) == len(by_title)

        by_highlights = client.get("/api/books", params={"sort": "highlights"}).json()
        counts = [b["total_highlights"] for b in by_highlights]
        assert counts == sorted(counts, reverse=True)
    finally:
        app.dependency_overrides.clear()
