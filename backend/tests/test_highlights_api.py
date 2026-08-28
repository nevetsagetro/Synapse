from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app.database import get_session
from app.main import app
from app.models.highlight import Highlight
from app.services.importer import import_clippings_file

FIXTURE = Path(__file__).parent / "fixtures" / "my_clippings_sample.txt"


def _client_with_fixture(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        import_clippings_file(FIXTURE, session)

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    return TestClient(app), engine


def test_favorites_and_hidden_listing_with_unhide(tmp_path: Path) -> None:
    client, engine = _client_with_fixture(tmp_path)
    try:
        with Session(engine) as session:
            highlight = session.exec(select(Highlight)).first()
            highlight_id = str(highlight.id)

        fav = client.post(f"/api/highlights/{highlight_id}/favorite")
        assert fav.status_code == 200
        favorites = client.get("/api/highlights/favorites")
        assert favorites.status_code == 200
        assert any(h["id"] == highlight_id for h in favorites.json())

        hide = client.post(f"/api/highlights/{highlight_id}/hidden")
        assert hide.status_code == 200
        hidden = client.get("/api/highlights/hidden")
        assert any(h["id"] == highlight_id for h in hidden.json())

        unhide = client.delete(f"/api/highlights/{highlight_id}/hidden")
        assert unhide.status_code == 200
        assert unhide.json()["is_hidden"] is False
        hidden_after = client.get("/api/highlights/hidden")
        assert not any(h["id"] == highlight_id for h in hidden_after.json())
    finally:
        app.dependency_overrides.clear()


def test_highlight_search(tmp_path: Path) -> None:
    client, _ = _client_with_fixture(tmp_path)
    try:
        response = client.get("/api/highlights/search", params={"q": "systems"})
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 1
        assert "systems" in results[0]["content"].lower()

        empty = client.get("/api/highlights/search", params={"q": "nonexistent phrase xyz"})
        assert empty.json() == []
    finally:
        app.dependency_overrides.clear()
