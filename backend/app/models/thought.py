from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class Thought(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    highlight_id: UUID = Field(foreign_key="highlight.id", index=True)
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
