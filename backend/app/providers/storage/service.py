import base64
import binascii
from dataclasses import dataclass
from typing import Protocol

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings


@dataclass(frozen=True, slots=True)
class PresignedUpload:
    url: str
    required_headers: dict[str, str]


@dataclass(frozen=True, slots=True)
class StoredObject:
    size_bytes: int
    mime_type: str
    checksum: str


class StorageError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class ObjectStorage(Protocol):
    def create_upload(
        self,
        *,
        storage_key: str,
        mime_type: str,
        checksum: str,
        expires_in_seconds: int,
    ) -> PresignedUpload: ...

    def verify_upload(
        self,
        *,
        storage_key: str,
        expected_size_bytes: int,
        expected_mime_type: str,
        expected_checksum: str,
    ) -> StoredObject: ...


class FixtureObjectStorage:
    def create_upload(
        self,
        *,
        storage_key: str,
        mime_type: str,
        checksum: str,
        expires_in_seconds: int,
    ) -> PresignedUpload:
        return PresignedUpload(
            url=f"https://storage.example.invalid/upload/{storage_key}",
            required_headers={
                "Content-Type": mime_type,
                "X-Content-SHA256": checksum,
            },
        )

    def verify_upload(
        self,
        *,
        storage_key: str,
        expected_size_bytes: int,
        expected_mime_type: str,
        expected_checksum: str,
    ) -> StoredObject:
        return StoredObject(
            size_bytes=expected_size_bytes,
            mime_type=expected_mime_type,
            checksum=expected_checksum,
        )


class S3ObjectStorage:
    def __init__(self, *, bucket: str, client: BaseClient) -> None:
        self.bucket = bucket
        self.client = client

    @staticmethod
    def _base64_checksum(hex_checksum: str) -> str:
        try:
            return base64.b64encode(bytes.fromhex(hex_checksum)).decode()
        except ValueError as exc:
            raise StorageError(
                "INVALID_CHECKSUM",
                "The SHA-256 checksum is invalid.",
                retryable=False,
            ) from exc

    def create_upload(
        self,
        *,
        storage_key: str,
        mime_type: str,
        checksum: str,
        expires_in_seconds: int,
    ) -> PresignedUpload:
        checksum_base64 = self._base64_checksum(checksum)
        try:
            url = self.client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self.bucket,
                    "Key": storage_key,
                    "ContentType": mime_type,
                    "ChecksumSHA256": checksum_base64,
                    "Metadata": {"sha256": checksum.lower()},
                },
                ExpiresIn=expires_in_seconds,
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageError(
                "OBJECT_STORAGE_UNAVAILABLE",
                "Object storage could not create an upload URL.",
                retryable=True,
            ) from exc
        return PresignedUpload(
            url=url,
            required_headers={
                "Content-Type": mime_type,
                "x-amz-checksum-sha256": checksum_base64,
                "x-amz-meta-sha256": checksum.lower(),
            },
        )

    def verify_upload(
        self,
        *,
        storage_key: str,
        expected_size_bytes: int,
        expected_mime_type: str,
        expected_checksum: str,
    ) -> StoredObject:
        try:
            response = self.client.head_object(
                Bucket=self.bucket,
                Key=storage_key,
                ChecksumMode="ENABLED",
            )
        except ClientError as exc:
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            code = exc.response.get("Error", {}).get("Code")
            if status == 404 or code in {"404", "NoSuchKey", "NotFound"}:
                raise StorageError(
                    "OBJECT_NOT_UPLOADED",
                    "The uploaded object was not found.",
                    retryable=False,
                ) from exc
            raise StorageError(
                "OBJECT_STORAGE_UNAVAILABLE",
                "Object storage could not verify the uploaded object.",
                retryable=True,
            ) from exc
        except BotoCoreError as exc:
            raise StorageError(
                "OBJECT_STORAGE_UNAVAILABLE",
                "Object storage could not verify the uploaded object.",
                retryable=True,
            ) from exc

        metadata = {
            str(key).lower(): str(value) for key, value in response.get("Metadata", {}).items()
        }
        checksum_base64 = response.get("ChecksumSHA256")
        if checksum_base64:
            try:
                actual_checksum = base64.b64decode(checksum_base64).hex()
            except (binascii.Error, ValueError):
                actual_checksum = ""
        else:
            actual_checksum = metadata.get("sha256", "")
        actual = StoredObject(
            size_bytes=int(response.get("ContentLength", -1)),
            mime_type=str(response.get("ContentType", "")),
            checksum=actual_checksum.lower(),
        )
        if (
            actual.size_bytes != expected_size_bytes
            or actual.mime_type != expected_mime_type
            or actual.checksum != expected_checksum.lower()
        ):
            raise StorageError(
                "UPLOAD_VERIFICATION_FAILED",
                "Uploaded object metadata does not match the upload intent.",
                retryable=False,
            )
        return actual


def build_object_storage(settings: Settings) -> ObjectStorage:
    if settings.object_storage_provider == "fixture":
        return FixtureObjectStorage()
    if settings.object_storage_provider != "s3" or not settings.object_storage_bucket:
        raise StorageError(
            "OBJECT_STORAGE_NOT_CONFIGURED",
            "Object storage is not configured.",
            retryable=False,
        )
    client_kwargs: dict[str, object] = {
        "region_name": settings.object_storage_region,
        "config": Config(
            signature_version="s3v4",
            s3={"addressing_style": settings.object_storage_addressing_style},
        ),
    }
    if settings.object_storage_endpoint_url:
        client_kwargs["endpoint_url"] = settings.object_storage_endpoint_url
    if settings.object_storage_access_key_id:
        client_kwargs["aws_access_key_id"] = settings.object_storage_access_key_id
    if settings.object_storage_secret_access_key:
        client_kwargs["aws_secret_access_key"] = (
            settings.object_storage_secret_access_key.get_secret_value()
        )
    if settings.object_storage_session_token:
        client_kwargs["aws_session_token"] = (
            settings.object_storage_session_token.get_secret_value()
        )
    return S3ObjectStorage(
        bucket=settings.object_storage_bucket,
        client=boto3.client("s3", **client_kwargs),
    )
