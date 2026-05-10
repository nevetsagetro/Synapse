from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import UUID

from sqlmodel import Session, select

from app.models.book import Book
from app.models.highlight import Highlight


@dataclass(frozen=True)
class SparkItem:
    highlight: Highlight
    book: Book | None


def select_daily_spark(session: Session, target_date: date | None = None) -> SparkItem | None:
    day = target_date or datetime.now(timezone.utc).date()
    highlights = session.exec(
        select(Highlight)
        .where(Highlight.is_hidden == False)  # noqa: E712
        .order_by(Highlight.created_at, Highlight.id)
    ).all()
    candidates = [highlight for highlight in highlights if highlight.content.strip() or (highlight.note or "").strip()]
    if not candidates:
        return None

    seed = int(hashlib.sha256(day.isoformat().encode("utf-8")).hexdigest(), 16)
    highlight = candidates[seed % len(candidates)]
    return SparkItem(highlight=highlight, book=session.get(Book, highlight.book_id))


def mark_highlight_seen(session: Session, highlight_id: UUID) -> Highlight | None:
    highlight = session.get(Highlight, highlight_id)
    if not highlight:
        return None
    now = datetime.now(timezone.utc)
    highlight.last_seen_at = now
    highlight.updated_at = now
    session.add(highlight)
    session.commit()
    session.refresh(highlight)
    return highlight


def set_highlight_favorite(session: Session, highlight_id: UUID, is_favorite: bool) -> Highlight | None:
    highlight = session.get(Highlight, highlight_id)
    if not highlight:
        return None
    highlight.is_favorite = is_favorite
    highlight.updated_at = datetime.now(timezone.utc)
    session.add(highlight)
    session.commit()
    session.refresh(highlight)
    return highlight


def set_highlight_hidden(session: Session, highlight_id: UUID, is_hidden: bool) -> Highlight | None:
    highlight = session.get(Highlight, highlight_id)
    if not highlight:
        return None
    highlight.is_hidden = is_hidden
    highlight.updated_at = datetime.now(timezone.utc)
    session.add(highlight)
    session.commit()
    session.refresh(highlight)
    return highlight


