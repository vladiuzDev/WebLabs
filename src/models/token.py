import uuid
from datetime import datetime, timezone

from beanie import Document
from pydantic import Field


class Token(Document):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: uuid.UUID
    token_hash: str
    token_type: str  # "access" or "refresh"
    expires_at: datetime
    is_revoked: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "tokens"
