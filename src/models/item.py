import uuid
from datetime import datetime, timezone
from typing import Annotated

from beanie import Document, Indexed
from pydantic import Field


class Item(Document):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: Annotated[str, Indexed(unique=True)]
    description: str
    status: str = "active"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: datetime | None = None

    class Settings:
        name = "items"
