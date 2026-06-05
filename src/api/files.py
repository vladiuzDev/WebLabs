from uuid import UUID

from fastapi import APIRouter, File as FileField, Security, UploadFile, status
from fastapi.responses import StreamingResponse

from src.core.middleware import get_current_user
from src.models.user import User
from src.schemas.file import FileRead
from src.services.file_service import FileService

router = APIRouter(prefix="/files", tags=["Files"])

_401 = {
    "description": "Unauthorized",
    "content": {"application/json": {"example": {"detail": "Not authenticated"}}},
}
_403 = {
    "description": "Forbidden — file belongs to another user",
    "content": {"application/json": {"example": {"detail": "Access denied"}}},
}
_404 = {
    "description": "File not found or deleted",
    "content": {"application/json": {"example": {"detail": "File not found"}}},
}
_413 = {
    "description": "File too large",
    "content": {"application/json": {"example": {"detail": "File too large. Maximum allowed size is 10485760 bytes."}}},
}


@router.post(
    "",
    response_model=FileRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file",
    description=(
        "Uploads a file via `multipart/form-data`. "
        "The file is streamed directly to MinIO — no full buffering in memory. "
        "Maximum file size: **10 MB** (configurable via `MAX_FILE_SIZE` env var). "
        "Returns file metadata; sensitive fields (`objectKey`, `bucket`) are hidden."
    ),
    responses={
        201: {
            "description": "File uploaded successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440002",
                        "original_name": "avatar.png",
                        "size": 204800,
                        "mimetype": "image/png",
                        "created_at": "2026-06-05T10:00:00Z",
                    }
                }
            },
        },
        401: _401,
        413: _413,
    },
)
async def upload_file(
    file: UploadFile = FileField(..., description="File to upload (multipart/form-data)"),
    current_user: User = Security(get_current_user),
) -> FileRead:
    service = FileService()
    file_doc = await service.upload(file, current_user.id)
    return FileRead.model_validate(file_doc)


@router.get(
    "/{file_id}",
    summary="Download a file",
    description=(
        "Streams the file content from MinIO. "
        "Only the file owner can download. "
        "Response includes `Content-Type`, `Content-Disposition` and `Content-Length` headers."
    ),
    responses={
        200: {"description": "File content stream"},
        401: _401,
        403: _403,
        404: _404,
    },
)
async def download_file(
    file_id: UUID,
    current_user: User = Security(get_current_user),
) -> StreamingResponse:
    service = FileService()
    file_doc = await service.get_by_id(file_id, current_user.id)
    minio_response = service.get_stream(file_doc.object_key)

    def _iter_stream():
        try:
            yield from minio_response.stream(32 * 1024)
        finally:
            minio_response.close()
            minio_response.release_conn()

    return StreamingResponse(
        _iter_stream(),
        media_type=file_doc.mimetype,
        headers={
            "Content-Disposition": f'attachment; filename="{file_doc.original_name}"',
            "Content-Length": str(file_doc.size),
        },
    )


@router.delete(
    "/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a file",
    description=(
        "Soft-deletes the file record in MongoDB and removes the object from MinIO. "
        "Only the file owner can delete."
    ),
    responses={
        204: {"description": "File deleted successfully"},
        401: _401,
        403: _403,
        404: _404,
    },
)
async def delete_file(
    file_id: UUID,
    current_user: User = Security(get_current_user),
) -> None:
    service = FileService()
    await service.delete(file_id, current_user.id)
