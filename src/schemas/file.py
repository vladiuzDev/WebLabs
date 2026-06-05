from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FileRead(BaseModel):
    id: UUID = Field(description="Unique file identifier (UUID)")
    original_name: str = Field(description="Original filename as uploaded")
    size: int = Field(description="File size in bytes")
    mimetype: str = Field(description="MIME type of the file")
    created_at: datetime = Field(description="Upload timestamp")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440002",
                    "original_name": "avatar.png",
                    "size": 204800,
                    "mimetype": "image/png",
                    "created_at": "2026-06-05T10:00:00Z",
                }
            ]
        },
    }
