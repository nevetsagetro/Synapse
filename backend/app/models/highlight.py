from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class Highlight(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    book_id: UUID = Field(foreign_key="book.id", index=True)
    content: str
    note: Optional[str] = None
    highlight_type: str = Field(default="highlight", index=True)
    page: Optional[int] = None
    location_start: Optional[int] = Field(default=None, index=True)
    location_end: Optional[int] = None
    date_added: Optional[datetime] = Field(default=None, index=True)
    source: str = Field(default="my_clippings", index=True)
    content_hash: str = Field(index=True)
    embedding: Optional[str] = None
    is_favorite: bool = False
    is_hidden: bool = False
    last_seen_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
