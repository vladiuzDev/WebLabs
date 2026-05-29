from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr = Field(
        description="User email address",
        examples=["user@example.com"],
    )
    password: str = Field(
        description="Password: min 8 chars, at least 1 uppercase letter and 1 digit",
        examples=["SecurePass123"],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{"email": "user@example.com", "password": "SecurePass123"}]
        }
    }

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    email: EmailStr = Field(
        description="Registered user email",
        examples=["user@example.com"],
    )
    password: str = Field(
        description="User password",
        examples=["SecurePass123"],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{"email": "user@example.com", "password": "SecurePass123"}]
        }
    }


class UserResponse(BaseModel):
    id: UUID = Field(
        description="Unique user identifier (UUID)",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    email: str | None = Field(
        description="User email address (null for OAuth-only accounts)",
        examples=["user@example.com"],
    )
    first_name: str | None = Field(
        description="User first name",
        examples=["John"],
    )
    last_name: str | None = Field(
        description="User last name",
        examples=["Doe"],
    )

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "email": "user@example.com",
                    "first_name": "John",
                    "last_name": "Doe",
                }
            ]
        },
    }


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(
        description="Email address associated with the account",
        examples=["user@example.com"],
    )

    model_config = {
        "json_schema_extra": {"examples": [{"email": "user@example.com"}]}
    }


class ResetPasswordRequest(BaseModel):
    token: str = Field(
        description="Password reset token received after calling /auth/forgot-password",
        examples=["v8Kx3mN9pQrL2wYjZ5tA1cE7hF4iG6uB"],
    )
    new_password: str = Field(
        description="New password: min 8 chars, at least 1 uppercase letter and 1 digit",
        examples=["NewSecurePass456"],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "token": "v8Kx3mN9pQrL2wYjZ5tA1cE7hF4iG6uB",
                    "new_password": "NewSecurePass456",
                }
            ]
        }
    }

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v
