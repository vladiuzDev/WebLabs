import asyncio
import uuid
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, UploadFile

from src.core.config import ALLOWED_IMAGE_TYPES, MAX_FILE_SIZE, MINIO_BUCKET
from src.models.file import File
from src.services.cache import cache, make_key
from src.services.storage import storage


def _meta_key(file_id: UUID) -> str:
    return make_key("files", str(file_id), "meta")


class FileService:
    async def upload(self, upload_file: UploadFile, user_id: UUID) -> File:
        # Determine size by seeking — no full memory buffer
        upload_file.file.seek(0, 2)
        size = upload_file.file.tell()
        upload_file.file.seek(0)

        if size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum allowed size is {MAX_FILE_SIZE} bytes.",
            )

        object_key = f"{uuid.uuid4()}/{upload_file.filename or 'file'}"
        content_type = upload_file.content_type or "application/octet-stream"

        # Stream upload to MinIO via thread (SDK is synchronous)
        await asyncio.to_thread(
            storage.upload_file,
            upload_file.file,
            size,
            object_key,
            content_type,
        )

        file_doc = File(
            user_id=user_id,
            original_name=upload_file.filename or "file",
            object_key=object_key,
            size=size,
            mimetype=content_type,
            bucket=MINIO_BUCKET,
        )
        await file_doc.insert()

        return file_doc

    async def get_by_id(self, file_id: UUID, user_id: UUID) -> File:
        key = _meta_key(file_id)
        cached = cache.get(key)
        if cached is not None:
            file_doc = File.model_validate(cached)
            if file_doc.deleted_at is not None:
                raise HTTPException(status_code=404, detail="File not found")
            if file_doc.user_id != user_id:
                raise HTTPException(status_code=403, detail="Access denied")
            return file_doc

        file_doc = await File.find_one(File.id == file_id, File.deleted_at == None)
        if file_doc is None:
            raise HTTPException(status_code=404, detail="File not found")
        if file_doc.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        cache.set(key, file_doc.model_dump(mode="json"))
        return file_doc

    async def delete(self, file_id: UUID, user_id: UUID) -> None:
        file_doc = await File.find_one(File.id == file_id, File.deleted_at == None)
        if file_doc is None:
            raise HTTPException(status_code=404, detail="File not found")
        if file_doc.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        await asyncio.to_thread(storage.delete_file, file_doc.object_key)

        file_doc.deleted_at = datetime.now(timezone.utc)
        await file_doc.save()

        cache.delete(_meta_key(file_id))

    def get_stream(self, object_key: str):
        return storage.get_file_stream(object_key)

    @staticmethod
    def validate_image_type(mimetype: str) -> None:
        if mimetype not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"Avatar must be an image. Allowed types: {', '.join(ALLOWED_IMAGE_TYPES)}",
            )
