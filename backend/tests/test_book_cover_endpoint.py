from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app.database import get_session
from app.main import app
from app.models.book import Book
from app.services.importer import import_clippings_file

FIXTURE = Path(__file__).parent / "fixtures" / "my_clippings_sample.txt"


def test_patch_book_cover_sets_and_clears(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        import_clippings_file(FIXTURE, session)
        book_id = str(session.exec(select(Book)).first().id)

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    client = TestClient(app)

    try:
        response = client.patch(f"/api/books/{book_id}/cover", json={"cover_url": "https://example.com/cover.jpg"})
        assert response.status_code == 200
        assert response.json()["cover_url"] == "https://example.com/cover.jpg"

        books = client.get("/api/books").json()
        assert next(b for b in books if b["id"] == book_id)["cover_url"] == "https://example.com/cover.jpg"

        cleared = client.patch(f"/api/books/{book_id}/cover", json={"cover_url": "  "})
        assert cleared.status_code == 200
        assert cleared.json()["cover_url"] is None

        missing = client.patch("/api/books/00000000-0000-0000-0000-000000000000/cover", json={"cover_url": "x"})
        assert missing.status_code == 404
    finally:
        app.dependency_overrides.clear()
