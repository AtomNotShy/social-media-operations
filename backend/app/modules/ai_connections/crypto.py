import base64
import binascii
import os
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import Settings
from app.core.errors import AppError


def _decode_key(value: str) -> bytes:
    try:
        key = base64.urlsafe_b64decode(value.encode())
    except (binascii.Error, ValueError) as exc:
        raise RuntimeError(
            "AI_CREDENTIALS_ENCRYPTION_KEY must be a base64-encoded 32-byte key"
        ) from exc
    if len(key) != 32:
        raise RuntimeError(
            "AI_CREDENTIALS_ENCRYPTION_KEY must be a base64-encoded 32-byte key"
        )
    return key


def _load_or_create_file_key(path: Path) -> bytes:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass
    try:
        return _decode_key(path.read_text(encoding="ascii").strip())
    except FileNotFoundError:
        encoded = base64.urlsafe_b64encode(AESGCM.generate_key(bit_length=256)).decode()
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return _decode_key(path.read_text(encoding="ascii").strip())
        with os.fdopen(descriptor, "w", encoding="ascii") as handle:
            handle.write(encoded)
            handle.write("\n")
        return _decode_key(encoded)


def credential_key(settings: Settings) -> bytes:
    configured = settings.ai_credentials_encryption_key
    if configured is not None:
        return _decode_key(configured.get_secret_value())
    if settings.app_env in {"staging", "production"}:
        raise RuntimeError(
            "AI_CREDENTIALS_ENCRYPTION_KEY must come from Secret Store in staging/production"
        )
    return _load_or_create_file_key(Path(settings.ai_credentials_key_file))


def _associated_data(workspace_id: object, connection_id: object) -> bytes:
    return f"social-ops:ai-connection:{workspace_id}:{connection_id}".encode()


def encrypt_api_key(
    settings: Settings,
    *,
    workspace_id: object,
    connection_id: object,
    api_key: str,
) -> str:
    nonce = os.urandom(12)
    ciphertext = AESGCM(credential_key(settings)).encrypt(
        nonce,
        api_key.encode(),
        _associated_data(workspace_id, connection_id),
    )
    return base64.urlsafe_b64encode(nonce + ciphertext).decode()


def decrypt_api_key(
    settings: Settings,
    *,
    workspace_id: object,
    connection_id: object,
    encrypted_api_key: str | None,
) -> str | None:
    if encrypted_api_key is None:
        return None
    try:
        payload = base64.urlsafe_b64decode(encrypted_api_key.encode())
        plaintext = AESGCM(credential_key(settings)).decrypt(
            payload[:12],
            payload[12:],
            _associated_data(workspace_id, connection_id),
        )
    except (binascii.Error, InvalidTag, ValueError) as exc:
        raise AppError(
            500,
            "AI_CREDENTIALS_UNAVAILABLE",
            "AI credentials cannot be decrypted",
            "The server-side AI credential key is missing or does not match this connection.",
        ) from exc
    return plaintext.decode()
