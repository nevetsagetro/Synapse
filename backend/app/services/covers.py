import re

import httpx
from sqlmodel import Session, select

from app.models.book import Book

OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
COVER_URL_TEMPLATE = "https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"

# Open Library's `title`/`author` search fields want a near-exact match, unlike
# a general full-text search. Kindle metadata is messy ("Book Title: Long
# Subtitle (Spanish Edition)", multiple co-authors joined with "and"), so we
# strip that noise before querying, and fall back to a title-only search.
_SUBTITLE_SPLIT = re.compile(r"\s*[:—-]\s")
_TRAILING_PARENS = re.compile(r"\s*\([^)]*\)\s*$")


def _clean_title(title: str) -> str:
    cleaned = _SUBTITLE_SPLIT.split(title, maxsplit=1)[0]
    cleaned = _TRAILING_PARENS.sub("", cleaned)
    return cleaned.strip() or title.strip()


def _first_author(author: str | None) -> str | None:
    if not author:
        return None
    first = re.split(r",| and ", author, maxsplit=1)[0]
    return first.strip() or None


def _query_open_library(params: dict[str, str | int]) -> int | None:
    try:
        response = httpx.get(OPEN_LIBRARY_SEARCH_URL, params=params, timeout=8.0)
        response.raise_for_status()
        docs = response.json().get("docs", [])
    except httpx.HTTPError:
        return None
    return docs[0].get("cover_i") if docs else None


def fetch_cover_url(title: str, author: str | None) -> str | None:
    """Look up a cover image for a book via the Open Library search API (no key required)."""
    clean_title = _clean_title(title)
    clean_author = _first_author(author)

    cover_id = None
    if clean_author:
        cover_id = _query_open_library({"title": clean_title, "author": clean_author, "limit": 1, "fields": "cover_i"})
    if not cover_id:
        # Retry without the author constraint — a slightly-off author string
        # (translators, "and" lists) shouldn't block finding a cover at all.
        cover_id = _query_open_library({"title": clean_title, "limit": 1, "fields": "cover_i"})

    if not cover_id:
        return None
    return COVER_URL_TEMPLATE.format(cover_id=cover_id)


def backfill_covers(session: Session) -> dict[str, int]:
    books = session.exec(select(Book).where(Book.cover_url.is_(None))).all()
    found = 0
    for book in books:
        cover_url = fetch_cover_url(book.title, book.author)
        if cover_url:
            book.cover_url = cover_url
            session.add(book)
            found += 1
    session.commit()
    return {"processed": len(books), "found": found}
