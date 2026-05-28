from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ItemCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=120,
        description="Unique item name (1–120 characters)",
        examples=["My First Item"],
    )
    description: str = Field(
        min_length=1,
        max_length=1000,
        description="Detailed item description (1–1000 characters)",
        examples=["This is a detailed description of my first item"],
    )
    status: str = Field(
        default="active",
        min_length=1,
        max_length=32,
        description="Item status (e.g. active, inactive, archived)",
        examples=["active"],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "My First Item",
                    "description": "This is a detailed description of my first item",
                    "status": "active",
                }
            ]
        }
    }


class ItemPut(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=120,
        description="New item name (1–120 characters)",
        examples=["Updated Item Name"],
    )
    description: str = Field(
        min_length=1,
        max_length=1000,
        description="New item description (1–1000 characters)",
        examples=["Updated description for the item"],
    )
    status: str = Field(
        min_length=1,
        max_length=32,
        description="New item status",
        examples=["inactive"],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Updated Item Name",
                    "description": "Updated description for the item",
                    "status": "inactive",
                }
            ]
        }
    }


class ItemPatch(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description="New item name (optional)",
        examples=["Patched Name"],
    )
    description: str | None = Field(
        default=None,
        min_length=1,
        max_length=1000,
        description="New item description (optional)",
        examples=["Patched description"],
    )
    status: str | None = Field(
        default=None,
        min_length=1,
        max_length=32,
        description="New item status (optional)",
        examples=["archived"],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{"status": "archived"}]
        }
    }


class ItemRead(BaseModel):
    id: UUID = Field(
        description="Unique item identifier (UUID)",
        examples=["550e8400-e29b-41d4-a716-446655440001"],
    )
    name: str = Field(
        description="Item name",
        examples=["My First Item"],
    )
    description: str = Field(
        description="Item description",
        examples=["This is a detailed description of my first item"],
    )
    status: str = Field(
        description="Item status",
        examples=["active"],
    )
    created_at: datetime = Field(
        description="ISO 8601 creation timestamp",
        examples=["2026-05-27T10:30:00Z"],
    )
    updated_at: datetime = Field(
        description="ISO 8601 last update timestamp",
        examples=["2026-05-27T12:00:00Z"],
    )

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440001",
                    "name": "My First Item",
                    "description": "This is a detailed description of my first item",
                    "status": "active",
                    "created_at": "2026-05-27T10:30:00Z",
                    "updated_at": "2026-05-27T12:00:00Z",
                }
            ]
        },
    }


class PaginationQuery(BaseModel):
    page: int = 1
    limit: int = 10

    @field_validator("page")
    @classmethod
    def validate_page(cls, value: int) -> int:
        if value < 1:
            raise ValueError("page must be greater than 0")
        return value

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, value: int) -> int:
        if value < 1 or value > 100:
            raise ValueError("limit must be in range 1..100")
        return value


class PaginationMeta(BaseModel):
    total: int = Field(description="Total number of items in the database", examples=[42])
    page: int = Field(description="Current page number", examples=[1])
    limit: int = Field(description="Number of items per page", examples=[10])
    totalPages: int = Field(description="Total number of pages", examples=[5])


class ItemListResponse(BaseModel):
    data: list[ItemRead] = Field(description="List of items on the current page")
    meta: PaginationMeta = Field(description="Pagination metadata")
