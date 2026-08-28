from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from app.models.book import Book


def normalize_identity(value: str) -> str:
    cleaned = re.sub(r"[﻿​‌‍]", "", value)
    return re.sub(r"\s+", " ", cleaned.strip().casefold())


def authors_compatible(author_a: Optional[str], author_b: Optional[str]) -> bool:
    """True if two author strings plausibly name the same book.

    Synapse's two import paths format authors very differently: My
    Clippings.txt stores just the primary author as "Last, First"; the
    Kindle Notebook scraper captures Amazon's full contributor line
    (translators, editors, "and"-joined lists) as "First Last, First2
    Last2, and First3 Last3". An exact string match after normalizing
    almost never holds even for the identical book, which used to split
    one book into two library entries with highlights duplicated across
    both. Instead we check whether one side's name tokens are fully
    contained in the other's, order- and punctuation-insensitive.

    Deliberately conservative: a single-word author (a mononym, or a
    normalization that reduces to one token) never matches a different
    string, and a two-token name must match completely. This favors
    leaving two genuinely different books unmerged over ever merging two
    different authors' highlights into one book.
    """
    norm_a, norm_b = normalize_identity(author_a or ""), normalize_identity(author_b or "")
    if not norm_a or not norm_b:
        return True
    if norm_a == norm_b:
        return True

    tokens_a = set(re.findall(r"[a-z0-9]+", norm_a))
    tokens_b = set(re.findall(r"[a-z0-9]+", norm_b))
    if len(tokens_a) < 2 or len(tokens_b) < 2:
        return False

    shorter, longer = (tokens_a, tokens_b) if len(tokens_a) <= len(tokens_b) else (tokens_b, tokens_a)
    return shorter <= longer


def get_or_create_book(session: Session, title: str, author: Optional[str], now: datetime) -> tuple[Book, bool]:
    normalized_title = normalize_identity(title)
    books = session.exec(select(Book)).all()
    for book in books:
        if normalize_identity(book.title) == normalized_title and authors_compatible(book.author, author):
            if not book.author and author:
                book.author = author
                session.add(book)
            return book, False

    book = Book(
        title=title,
        author=author,
        first_imported_at=now,
        last_imported_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(book)
    session.flush()
    session.refresh(book)
    return book, True
