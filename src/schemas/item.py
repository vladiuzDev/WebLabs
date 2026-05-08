from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1000)
    status: str = Field(default="active", min_length=1, max_length=32)


class ItemPut(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1000)
    status: str = Field(min_length=1, max_length=32)


class ItemPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, min_length=1, max_length=1000)
    status: str | None = Field(default=None, min_length=1, max_length=32)


class ItemRead(BaseModel):
    id: UUID
    name: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


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
    total: int
    page: int
    limit: int
    totalPages: int


class ItemListResponse(BaseModel):
    data: list[ItemRead]
    meta: PaginationMeta
