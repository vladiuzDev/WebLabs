from uuid import UUID

from pydantic import BaseModel, Field


class ProfileUpdate(BaseModel):
    first_name: str | None = Field(default=None, description="First name")
    last_name: str | None = Field(default=None, description="Last name")
    display_name: str | None = Field(default=None, max_length=100, description="Display name")
    bio: str | None = Field(default=None, max_length=500, description="Short biography")
    avatar_file_id: UUID | None = Field(default=None, description="UUID of a previously uploaded image file")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "first_name": "Ivan",
                    "last_name": "Petrov",
                    "display_name": "ivan_p",
                    "bio": "Backend developer",
                    "avatar_file_id": "550e8400-e29b-41d4-a716-446655440002",
                }
            ]
        }
    }


class ProfileResponse(BaseModel):
    id: UUID = Field(description="User UUID")
    email: str | None = Field(description="Email address")
    first_name: str | None = Field(description="First name")
    last_name: str | None = Field(description="Last name")
    display_name: str | None = Field(description="Display name")
    bio: str | None = Field(description="Short biography")
    avatar_file_id: UUID | None = Field(description="Avatar file UUID")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "email": "user@example.com",
                    "first_name": "Ivan",
                    "last_name": "Petrov",
                    "display_name": "ivan_p",
                    "bio": "Backend developer",
                    "avatar_file_id": "550e8400-e29b-41d4-a716-446655440002",
                }
            ]
        },
    }
