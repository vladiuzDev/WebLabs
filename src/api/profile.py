from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Security, status

from src.core.middleware import get_current_user
from src.models.file import File
from src.models.user import User
from src.schemas.profile import ProfileResponse, ProfileUpdate
from src.services.cache import cache, make_key
from src.services.file_service import FileService

router = APIRouter(prefix="/profile", tags=["Profile"])

_401 = {
    "description": "Unauthorized",
    "content": {"application/json": {"example": {"detail": "Not authenticated"}}},
}


@router.get(
    "",
    response_model=ProfileResponse,
    summary="Get current user profile",
    description="Returns the full profile of the authenticated user including avatar and bio.",
    responses={
        200: {
            "description": "User profile",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "email": "user@example.com",
                        "first_name": "Ivan",
                        "last_name": "Petrov",
                        "display_name": "ivan_p",
                        "bio": "Backend developer",
                        "avatar_file_id": None,
                    }
                }
            },
        },
        401: _401,
    },
)
async def get_profile(
    current_user: User = Security(get_current_user),
) -> ProfileResponse:
    cache_key = make_key("users", "profile", str(current_user.id))
    cached = cache.get(cache_key)
    if cached is not None:
        return ProfileResponse.model_validate(cached)

    data = ProfileResponse.model_validate(current_user).model_dump(mode="json")
    cache.set(cache_key, data)
    return ProfileResponse.model_validate(current_user)


@router.post(
    "",
    response_model=ProfileResponse,
    summary="Update current user profile",
    description=(
        "Updates profile fields. All fields are optional — only provided fields are changed. "
        "To set an avatar, first upload an image via **POST /files** and pass the returned `id` as `avatarFileId`. "
        "The system verifies that the file belongs to the current user and is an image (png/jpeg/jpg)."
    ),
    responses={
        200: {
            "description": "Updated profile",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "email": "user@example.com",
                        "first_name": "Ivan",
                        "last_name": "Petrov",
                        "display_name": "ivan_p",
                        "bio": "Backend developer",
                        "avatar_file_id": "550e8400-e29b-41d4-a716-446655440002",
                    }
                }
            },
        },
        401: _401,
        403: {
            "description": "File belongs to another user",
            "content": {"application/json": {"example": {"detail": "Access denied"}}},
        },
        404: {
            "description": "Avatar file not found",
            "content": {"application/json": {"example": {"detail": "Avatar file not found"}}},
        },
        422: {
            "description": "File is not an image",
            "content": {"application/json": {"example": {"detail": "Avatar must be an image (png, jpeg, jpg)"}}},
        },
    },
)
async def update_profile(
    body: ProfileUpdate,
    current_user: User = Security(get_current_user),
) -> ProfileResponse:
    if body.avatar_file_id is not None:
        file_doc = await File.find_one(File.id == body.avatar_file_id, File.deleted_at == None)
        if file_doc is None:
            raise HTTPException(status_code=404, detail="Avatar file not found")
        if file_doc.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        FileService.validate_image_type(file_doc.mimetype)
        current_user.avatar_file_id = body.avatar_file_id

    if body.first_name is not None:
        current_user.first_name = body.first_name
    if body.last_name is not None:
        current_user.last_name = body.last_name
    if body.display_name is not None:
        current_user.display_name = body.display_name
    if body.bio is not None:
        current_user.bio = body.bio

    current_user.updated_at = datetime.now(timezone.utc)
    await current_user.save()

    cache.delete(make_key("users", "profile", str(current_user.id)))
    return ProfileResponse.model_validate(current_user)
