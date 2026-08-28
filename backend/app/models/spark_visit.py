from datetime import date as date_type, datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class SparkVisit(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    visited_date: date_type = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
