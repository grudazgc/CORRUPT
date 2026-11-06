"""Wallet authentication with Solana signatures and short-lived JWTs."""

from __future__ import annotations

import datetime as dt
import secrets

import jwt
from fastapi import Depends, Header, HTTPException, status
from solders.pubkey import Pubkey
from solders.signature import Signature
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import AuthChallenge, Wallet, get_db, utcnow

CHALLENGE_TEMPLATE = (
    "{app_name} authentication\n"
    "Wallet: {wallet}\n"
    "Nonce: {nonce}\n"
    "Issued At: {issued_at}\n"
    "This signature proves wallet ownership. It costs nothing and is not a transaction."
)


class AuthError(HTTPException):
    def __init__(self, detail: str, code: int = status.HTTP_401_UNAUTHORIZED) -> None:
        super().__init__(status_code=code, detail=detail)


def create_challenge(db: Session, wallet: str) -> AuthChallenge:
    _validate_pubkey(wallet)
    settings = get_settings()
    nonce = secrets.token_hex(16)
    issued_at = utcnow()
    message = CHALLENGE_TEMPLATE.format(
        app_name=settings.app_name,
        wallet=wallet,
        nonce=nonce,
        issued_at=issued_at.isoformat(),
    )
    challenge = AuthChallenge(
        wallet=wallet,
        nonce=nonce,
        message=message,
        expires_at=issued_at + dt.timedelta(seconds=settings.challenge_ttl_seconds),
    )
    db.add(challenge)
    db.flush()
    return challenge


def _validate_pubkey(value: str) -> Pubkey:
    try:
        return Pubkey.from_string(value)
    except Exception as exc:  # noqa: BLE001 - surfaced as a client error
        raise AuthError("wallet is not a valid base58 Solana address", 400) from exc


def consume_challenge(db: Session, wallet: str, signature: str) -> AuthChallenge:
    challenge = db.execute(
        select(AuthChallenge)
        .where(AuthChallenge.wallet == wallet, AuthChallenge.consumed_at.is_(None))
        .order_by(AuthChallenge.id.desc())
    ).scalars().first()
    if challenge is None:
        raise AuthError("no active challenge for this wallet; request a new one")

    now = utcnow()
    expires_at = challenge.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=dt.timezone.utc)
    if expires_at < now:
        raise AuthError("challenge has expired; request a new one")

    try:
        signature_bytes = Signature.from_string(signature)
    except Exception as exc:  # noqa: BLE001
        raise AuthError("signature is not valid base58", 400) from exc

    pubkey = _validate_pubkey(wallet)
    if not signature_bytes.verify(pubkey, challenge.message.encode()):
        raise AuthError("signature does not match the challenge message")

    challenge.consumed_at = now
    db.flush()
    return challenge


def get_or_create_wallet(db: Session, wallet: str) -> Wallet:
    record = db.execute(select(Wallet).where(Wallet.address == wallet)).scalar_one_or_none()
    if record is None:
        record = Wallet(address=wallet, role="reporter")
        db.add(record)
        db.flush()
    return record


def issue_token(wallet: Wallet) -> tuple[str, int]:
    settings = get_settings()
    expires_in = settings.jwt_ttl_seconds
    now = utcnow()
    payload = {
        "sub": wallet.address,
        "role": wallet.role,
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(seconds=expires_in)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_in


def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("token has expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("token is invalid") from exc


def current_wallet(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Wallet:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("missing bearer token")
    claims = decode_token(authorization.split(" ", 1)[1].strip())
    address = claims.get("sub")
    wallet = db.execute(select(Wallet).where(Wallet.address == address)).scalar_one_or_none()
    if wallet is None:
        raise AuthError("wallet is not registered")
    return wallet


def require_api_key(api_key: str | None, expected: str, role: str) -> None:
    if not api_key or not secrets.compare_digest(api_key, expected):
        raise AuthError(f"{role} API key is missing or invalid", status.HTTP_403_FORBIDDEN)


def require_admin(
    x_api_key: str | None = Header(default=None, alias="X-Admin-Key"),
) -> None:
    require_api_key(x_api_key, get_settings().admin_api_key, "admin")


def require_verifier(
    x_api_key: str | None = Header(default=None, alias="X-Verifier-Key"),
) -> None:
    require_api_key(x_api_key, get_settings().verifier_api_key, "verifier")
