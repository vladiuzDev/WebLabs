import uuid
from datetime import datetime, timezone

from beanie import Document
from pydantic import Field


class PasswordReset(Document):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: uuid.UUID
    token_hash: str
    expires_at: datetime
    is_used: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "password_resets"
