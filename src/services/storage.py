import logging

from minio import Minio
from minio.error import S3Error

from src.core.config import MINIO_ACCESS_KEY, MINIO_BUCKET, MINIO_ENDPOINT, MINIO_SECRET_KEY, MINIO_USE_SSL

logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self) -> None:
        self._client = Minio(
            endpoint=MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_USE_SSL,
        )
        self._bucket = MINIO_BUCKET

    def ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)
            logger.info("Created MinIO bucket: %s", self._bucket)

    def upload_file(self, data, size: int, object_key: str, content_type: str) -> None:
        """Upload file stream to MinIO without fully buffering in memory."""
        self._client.put_object(
            bucket_name=self._bucket,
            object_name=object_key,
            data=data,
            length=size,
            content_type=content_type,
        )

    def get_file_stream(self, object_key: str):
        """Return a streaming response from MinIO."""
        return self._client.get_object(self._bucket, object_key)

    def delete_file(self, object_key: str) -> None:
        try:
            self._client.remove_object(self._bucket, object_key)
        except S3Error as exc:
            logger.warning("MinIO delete error for %s: %s", object_key, exc)

    def file_exists(self, object_key: str) -> bool:
        try:
            self._client.stat_object(self._bucket, object_key)
            return True
        except S3Error:
            return False


storage = StorageService()
