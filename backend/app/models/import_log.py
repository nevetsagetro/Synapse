from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class ImportLog(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    source: str = Field(index=True)
    file_name: Optional[str] = None
    records_seen: int = 0
    records_created: int = 0
    records_skipped: int = 0
    records_failed: int = 0
    error_summary: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
