from pathlib import Path

import httpx
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.book import Book
from app.services.covers import backfill_covers, fetch_cover_url
from app.services.importer import import_clippings_file

FIXTURE = Path(__file__).parent / "fixtures" / "my_clippings_sample.txt"


def test_fetch_cover_url_parses_open_library_response(monkeypatch) -> None:
    def fake_get(url, params=None, timeout=None):
        request = httpx.Request("GET", url, params=params)
        return httpx.Response(200, json={"docs": [{"cover_i": 12345}]}, request=request)

    monkeypatch.setattr(httpx, "get", fake_get)
    assert fetch_cover_url("Atomic Habits", "James Clear") == "https://covers.openlibrary.org/b/id/12345-M.jpg"


def test_fetch_cover_url_returns_none_without_match(monkeypatch) -> None:
    def fake_get(url, params=None, timeout=None):
        request = httpx.Request("GET", url, params=params)
        return httpx.Response(200, json={"docs": []}, request=request)

    monkeypatch.setattr(httpx, "get", fake_get)
    assert fetch_cover_url("Some Unknown Title", None) is None


def test_fetch_cover_url_strips_subtitle_and_parenthetical() -> None:
    # Real Open Library titles are matched near-exactly, so Kindle-style
    # "Title: Subtitle (Spanish Edition)" metadata has to be trimmed first.
    from app.services.covers import _clean_title

    assert _clean_title("Hyperfocus: How to Work Less and Achieve More") == "Hyperfocus"
    assert _clean_title("La agonía del Eros (Spanish Edition)") == "La agonía del Eros"


def test_fetch_cover_url_falls_back_to_title_only_when_author_search_misses(monkeypatch) -> None:
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(params)
        request = httpx.Request("GET", url, params=params)
        if "author" in params:
            return httpx.Response(200, json={"docs": []}, request=request)
        return httpx.Response(200, json={"docs": [{"cover_i": 42}]}, request=request)

    monkeypatch.setattr(httpx, "get", fake_get)
    result = fetch_cover_url("La agonía del Eros (Spanish Edition)", "Byung-Chul Han, Antoni Martínez Riu")

    assert result == "https://covers.openlibrary.org/b/id/42-M.jpg"
    assert len(calls) == 2
    assert calls[0]["author"] == "Byung-Chul Han"
    assert "author" not in calls[1]


def test_backfill_covers_populates_missing_books(tmp_path: Path, monkeypatch) -> None:
    def fake_get(url, params=None, timeout=None):
        request = httpx.Request("GET", url, params=params)
        return httpx.Response(200, json={"docs": [{"cover_i": 999}]}, request=request)

    monkeypatch.setattr(httpx, "get", fake_get)

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        import_clippings_file(FIXTURE, session)
        result = backfill_covers(session)
        assert result["found"] == result["processed"]

        books = session.exec(select(Book)).all()
        assert all(book.cover_url == "https://covers.openlibrary.org/b/id/999-M.jpg" for book in books)
