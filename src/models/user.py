import uuid
from datetime import datetime, timezone

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class User(Document):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    email: str | None = None
    password_hash: str | None = None
    salt: str | None = None
    yandex_id: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: datetime | None = None

    class Settings:
        name = "users"
        indexes = [
            IndexModel([("email", ASCENDING)], unique=True, sparse=True),
            IndexModel([("yandex_id", ASCENDING)], unique=True, sparse=True),
        ]
