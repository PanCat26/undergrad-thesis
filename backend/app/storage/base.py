import os
from typing import Protocol

from botocore.exceptions import BotoCoreError, ClientError

from app.config import get_settings
from app.core.aws import boto3_client
from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger

logger = get_logger("app.storage")


class Storage(Protocol):
    """Blob storage for uploaded source files (local disk in dev, S3 in prod)."""

    def save(self, key: str, data: bytes) -> None: ...

    def read(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


class LocalDiskStorage:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir

    def _path(self, key: str) -> str:
        path = os.path.normpath(os.path.join(self.base_dir, key))
        if not path.startswith(os.path.normpath(self.base_dir)):
            raise ValueError("Invalid storage key")
        return path

    def save(self, key: str, data: bytes) -> None:
        path = self._path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(data)

    def read(self, key: str) -> bytes:
        with open(self._path(key), "rb") as handle:
            return handle.read()

    def delete(self, key: str) -> None:
        try:
            os.remove(self._path(key))
        except FileNotFoundError:
            pass


class S3Storage:
    def __init__(self, bucket: str):
        self.bucket = bucket
        self._client = boto3_client("s3", get_settings())

    def save(self, key: str, data: bytes) -> None:
        try:
            self._client.put_object(Bucket=self.bucket, Key=key, Body=data)
        except (ClientError, BotoCoreError) as exc:
            logger.error("S3 put_object failed", exc_info=exc)
            raise ExternalServiceError("Failed to store the file") from exc

    def read(self, key: str) -> bytes:
        try:
            return self._client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except (ClientError, BotoCoreError) as exc:
            logger.error("S3 get_object failed", exc_info=exc)
            raise ExternalServiceError("Failed to read the file") from exc

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self.bucket, Key=key)
        except (ClientError, BotoCoreError) as exc:
            logger.error("S3 delete_object failed", exc_info=exc)
            raise ExternalServiceError("Failed to delete the file") from exc


def get_storage() -> Storage:
    settings = get_settings()
    if settings.storage_backend == "s3":
        if not settings.s3_bucket:
            raise ExternalServiceError("S3 bucket is not configured")
        return S3Storage(settings.s3_bucket)
    return LocalDiskStorage(settings.local_storage_dir)
