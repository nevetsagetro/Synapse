from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app
from app.services.importer import import_clippings_file


def test_summary_and_books_actions(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    fixture = Path(__file__).parent / "fixtures" / "my_clippings_sample.txt"

    with Session(engine) as session:
        import_clippings_file(fixture, session)

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    client = TestClient(app)

    try:
        summary = client.get("/api/summary")
        books = client.get("/api/books")

        assert summary.status_code == 200
        assert summary.json()["books"] == 4
        assert summary.json()["highlights"] == 4

        assert books.status_code == 200
        assert len(books.json()) == 4

        first_book_id = books.json()[0]["id"]
        detail = client.get(f"/api/books/{first_book_id}")
        assert detail.status_code == 200
        assert "book" in detail.json()
        assert "highlights" in detail.json()
    finally:
        app.dependency_overrides.clear()


def test_upload_import_action(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    fixture = Path(__file__).parent / "fixtures" / "my_clippings_sample.txt"

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    client = TestClient(app)

    try:
        with fixture.open("rb") as file_obj:
            response = client.post(
                "/api/import/upload",
                files={"file": ("My Clippings.txt", file_obj, "text/plain")},
            )

        assert response.status_code == 200
        assert response.json()["records_created"] == 4
        assert response.json()["file_name"] == "My Clippings.txt"
    finally:
        app.dependency_overrides.clear()
