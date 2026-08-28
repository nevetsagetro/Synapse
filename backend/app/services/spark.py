from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlmodel import Session, select

from app.models.book import Book
from app.models.highlight import Highlight
from app.models.spark_visit import SparkVisit


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


def get_on_this_day_highlights(session: Session, target_date: date | None = None) -> list[SparkItem]:
    """Highlights added on this calendar day in a previous year."""
    day = target_date or datetime.now(timezone.utc).date()
    highlights = session.exec(
        select(Highlight).where(
            Highlight.is_hidden == False,  # noqa: E712
            Highlight.date_added.is_not(None),
        )
    ).all()
    matches = [
        h
        for h in highlights
        if h.date_added.month == day.month and h.date_added.day == day.day and h.date_added.year < day.year
    ]
    matches.sort(key=lambda h: h.date_added, reverse=True)
    return [SparkItem(highlight=h, book=session.get(Book, h.book_id)) for h in matches]


def record_spark_visit(session: Session, target_date: date | None = None) -> None:
    """Log that Spark was opened today, for streak tracking. No-op if already logged."""
    day = target_date or datetime.now(timezone.utc).date()
    existing = session.exec(select(SparkVisit).where(SparkVisit.visited_date == day)).first()
    if existing:
        return
    session.add(SparkVisit(visited_date=day))
    session.commit()


def get_spark_streak(session: Session, target_date: date | None = None) -> dict[str, int]:
    today = target_date or datetime.now(timezone.utc).date()
    visited_days = set(session.exec(select(SparkVisit.visited_date)).all())

    current_streak = 0
    cursor = today if today in visited_days else today - timedelta(days=1)
    while cursor in visited_days:
        current_streak += 1
        cursor -= timedelta(days=1)

    longest_streak = 0
    run = 0
    for day in sorted(visited_days):
        run = run + 1 if (day - timedelta(days=1)) in visited_days else 1
        longest_streak = max(longest_streak, run)

    return {
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "total_days": len(visited_days),
    }


