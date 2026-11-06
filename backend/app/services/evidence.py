"""Evidence storage.

Evidence is attacker-controlled input, so it is stored outside the database
under a content-addressed name. When an encryption key is configured the
bytes are encrypted at rest with Fernet (AES-128-CBC + HMAC); otherwise the
deployment is expected to provide an encrypted volume.
"""

from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings

ALLOWED_MEDIA_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "text/plain",
    "text/csv",
    "application/zip",
    "application/json",
    "audio/mpeg",
    "video/mp4",
    "application/octet-stream",
}


class EvidenceError(ValueError):
    """Raised when evidence fails validation."""


@dataclass(frozen=True)
class StoredEvidence:
    digest: str
    size: int
    path: str
    encrypted: bool


def _fernet():
    settings = get_settings()
    if not settings.evidence_encryption_key:
        return None
    from cryptography.fernet import Fernet

    key = settings.evidence_encryption_key.encode()
    try:
        return Fernet(key)
    except ValueError:
        # Allow raw 32-byte keys to be supplied as hex or base64.
        raw = base64.urlsafe_b64encode(hashlib.sha256(key).digest())
        return Fernet(raw)


def validate_upload(media_type: str, payload: bytes) -> None:
    settings = get_settings()
    if len(payload) == 0:
        raise EvidenceError("evidence file is empty")
    if len(payload) > settings.max_evidence_bytes:
        raise EvidenceError(
            f"evidence exceeds the {settings.max_evidence_bytes} byte limit"
        )
    if media_type not in ALLOWED_MEDIA_TYPES:
        raise EvidenceError(f"unsupported media type: {media_type}")


def store_evidence(report_token: str, filename: str, media_type: str, payload: bytes) -> StoredEvidence:
    """Persists evidence and returns its digest and location.

    The digest is always computed over the *plaintext* so the on-chain
    commitment matches what a whistleblower originally submitted.
    """

    validate_upload(media_type, payload)
    digest = hashlib.sha256(payload).hexdigest()
    settings = get_settings()
    suffix = Path(filename).suffix[:16]
    target = settings.evidence_dir / f"{report_token}-{digest[:16]}{suffix}"

    fernet = _fernet()
    if fernet is not None:
        target.write_bytes(fernet.encrypt(payload))
        encrypted = True
    else:
        target.write_bytes(payload)
        encrypted = False

    os.chmod(target, 0o600)
    return StoredEvidence(
        digest=digest, size=len(payload), path=str(target), encrypted=encrypted
    )


def read_evidence(path: str) -> bytes:
    raw = Path(path).read_bytes()
    fernet = _fernet()
    if fernet is not None:
        return fernet.decrypt(raw)
    return raw


def verify_evidence(path: str, expected_digest: str) -> bool:
    """Confirms stored evidence still matches the on-chain commitment."""

    try:
        payload = read_evidence(path)
    except (OSError, ValueError):
        return False
    return hashlib.sha256(payload).hexdigest() == expected_digest
