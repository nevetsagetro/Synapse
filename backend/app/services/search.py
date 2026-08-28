from sqlmodel import Session, select, or_

from app.models.highlight import Highlight


def search_highlights(session: Session, query: str, limit: int = 50) -> list[Highlight]:
    q = query.strip()
    if not q:
        return []
    like = f"%{q}%"
    return session.exec(
        select(Highlight)
        .where(or_(Highlight.content.ilike(like), Highlight.note.ilike(like)))
        .order_by(Highlight.date_added.desc())
        .limit(limit)
    ).all()
