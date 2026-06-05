import uuid
from datetime import datetime, timezone

from beanie import Document
from pydantic import Field


class File(Document):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: uuid.UUID
    original_name: str
    object_key: str
    size: int
    mimetype: str
    bucket: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: datetime | None = None

    class Settings:
        name = "files"
