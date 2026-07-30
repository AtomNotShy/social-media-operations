import base64

import pytest

from app.providers.storage import S3ObjectStorage, StorageError


class FakeS3Client:
    def __init__(self):
        self.presign_call = None
        self.head_call = None
        self.head_response = {}

    def generate_presigned_url(self, operation, *, Params, ExpiresIn):
        self.presign_call = (operation, Params, ExpiresIn)
        return "https://bucket.example.test/presigned"

    def head_object(self, **kwargs):
        self.head_call = kwargs
        return self.head_response


def test_s3_presign_binds_type_checksum_and_metadata():
    client = FakeS3Client()
    storage = S3ObjectStorage(bucket="assets", client=client)
    checksum = "ab" * 32

    upload = storage.create_upload(
        storage_key="workspace/project/asset",
        mime_type="image/png",
        checksum=checksum,
        expires_in_seconds=900,
    )

    checksum_base64 = base64.b64encode(bytes.fromhex(checksum)).decode()
    operation, params, expires = client.presign_call
    assert operation == "put_object"
    assert expires == 900
    assert params == {
        "Bucket": "assets",
        "Key": "workspace/project/asset",
        "ContentType": "image/png",
        "ChecksumSHA256": checksum_base64,
        "Metadata": {"sha256": checksum},
    }
    assert upload.required_headers["x-amz-checksum-sha256"] == checksum_base64
    assert upload.required_headers["x-amz-meta-sha256"] == checksum


def test_s3_completion_verifies_remote_object_metadata():
    client = FakeS3Client()
    checksum = "cd" * 32
    client.head_response = {
        "ContentLength": 1024,
        "ContentType": "image/png",
        "ChecksumSHA256": base64.b64encode(bytes.fromhex(checksum)).decode(),
        "Metadata": {"sha256": checksum},
    }
    storage = S3ObjectStorage(bucket="assets", client=client)

    result = storage.verify_upload(
        storage_key="workspace/project/asset",
        expected_size_bytes=1024,
        expected_mime_type="image/png",
        expected_checksum=checksum,
    )

    assert result.checksum == checksum
    assert client.head_call == {
        "Bucket": "assets",
        "Key": "workspace/project/asset",
        "ChecksumMode": "ENABLED",
    }


def test_s3_completion_rejects_metadata_mismatch():
    client = FakeS3Client()
    client.head_response = {
        "ContentLength": 1,
        "ContentType": "image/png",
        "Metadata": {"sha256": "ef" * 32},
    }
    storage = S3ObjectStorage(bucket="assets", client=client)

    with pytest.raises(StorageError, match="does not match") as captured:
        storage.verify_upload(
            storage_key="workspace/project/asset",
            expected_size_bytes=1024,
            expected_mime_type="image/png",
            expected_checksum="ef" * 32,
        )

    assert captured.value.code == "UPLOAD_VERIFICATION_FAILED"
