from collections import defaultdict
from typing import Any

from sqlmodel import Session, func, select

from app.models.book import Book
from app.models.highlight import Highlight
from app.models.import_log import ImportLog


def get_insights_summary(session: Session) -> dict[str, Any]:
    # Basic counts
    total_books = session.exec(select(func.count(Book.id))).one()
    total_highlights = session.exec(select(func.count(Highlight.id))).one()
    total_imports = session.exec(select(func.count(ImportLog.id))).one()
    latest_import = session.exec(select(ImportLog).order_by(ImportLog.created_at.desc())).first()

    # Timeline: Highlights per month
    timeline_query = select(
        func.strftime("%Y-%m", Highlight.date_added).label("month"), func.count(Highlight.id).label("count")
    ).where(Highlight.date_added.is_not(None)).group_by("month").order_by("month")
    
    timeline_rows = session.exec(timeline_query).all()
    timeline = [{"month": row[0], "count": row[1]} for row in timeline_rows if row[0]]

    # Top Authors
    authors_query = select(
        Book.author, func.sum(Book.total_highlights).label("highlights"), func.count(Book.id).label("books")
    ).where(Book.author.is_not(None)).group_by(Book.author).order_by(func.sum(Book.total_highlights).desc()).limit(10)
    
    author_rows = session.exec(authors_query).all()
    top_authors = [{"name": row[0], "total_highlights": row[1] or 0, "total_books": row[2] or 0} for row in author_rows]

    # Books to revisit: Books with high highlights that haven't been recently seen
    # We can approximate this by just picking the top books by highlight count.
    # To make it "revisit", we can prioritize older imports or just the top 5.
    books_query = select(Book).where(Book.total_highlights > 0).order_by(Book.total_highlights.desc()).limit(5)
    books_rows = session.exec(books_query).all()
    books_to_revisit = [
        {
            "id": str(book.id),
            "title": book.title,
            "author": book.author,
            "total_highlights": book.total_highlights,
        }
        for book in books_rows
    ]

    # Habit Signals
    favorite_count = session.exec(select(func.count(Highlight.id)).where(Highlight.is_favorite == True)).one()  # noqa: E712
    hidden_count = session.exec(select(func.count(Highlight.id)).where(Highlight.is_hidden == True)).one()  # noqa: E712
    seen_count = session.exec(select(func.count(Highlight.id)).where(Highlight.last_seen_at.is_not(None))).one()

    return {
        "summary": {
            "books": total_books,
            "highlights": total_highlights,
            "imports": total_imports,
            "latest_import_at": latest_import.created_at.isoformat() if latest_import else None,
        },
        "timeline": timeline,
        "top_authors": top_authors,
        "books_to_revisit": books_to_revisit,
        "signals": {
            "favorites": favorite_count,
            "hidden": hidden_count,
            "seen": seen_count,
        },
    }
