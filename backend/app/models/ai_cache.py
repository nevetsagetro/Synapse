from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class AIRecommendationCache(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    recommendations_json: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
