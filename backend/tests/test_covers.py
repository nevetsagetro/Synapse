from pathlib import Path

import httpx
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.book import Book
from app.services.covers import backfill_covers, fetch_cover_url, set_manual_cover
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


def test_backfill_covers_handles_no_missing_books(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        result = backfill_covers(session)

    assert result == {"processed": 0, "found": 0}


def test_backfill_covers_fetches_concurrently(tmp_path: Path, monkeypatch) -> None:
    # Each book's lookup used to be a fully sequential HTTP round trip; this
    # confirms multiple lookups can be in flight at once rather than one
    # strictly waiting for the previous one to finish.
    import threading
    import time

    concurrent_calls = []
    lock = threading.Lock()

    def fake_get(url, params=None, timeout=None):
        with lock:
            concurrent_calls.append(1)
        time.sleep(0.2)
        with lock:
            concurrent_calls.append(-1)
        request = httpx.Request("GET", url, params=params)
        return httpx.Response(200, json={"docs": [{"cover_i": 1}]}, request=request)

    monkeypatch.setattr(httpx, "get", fake_get)

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        import_clippings_file(FIXTURE, session)
        books_before = session.exec(select(Book)).all()
        assert len(books_before) > 1, "fixture needs more than one book for this test to mean anything"

        backfill_covers(session)

    max_concurrent = 0
    running = 0
    for delta in concurrent_calls:
        running += delta
        max_concurrent = max(max_concurrent, running)
    assert max_concurrent > 1, "lookups should overlap, not run strictly one at a time"


def test_set_manual_cover(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        import_clippings_file(FIXTURE, session)
        book = session.exec(select(Book)).first()

        updated = set_manual_cover(session, book, "https://example.com/my-cover.jpg")
        assert updated.cover_url == "https://example.com/my-cover.jpg"

        cleared = set_manual_cover(session, book, None)
        assert cleared.cover_url is None
