"""Minimal Borsh encoder for the instruction arguments this platform sends.

Only the subset of Borsh used by the ``corrupt_rewards`` program is
implemented, which keeps the dependency surface small and the encoding
explicit and testable.
"""

from __future__ import annotations

import hashlib
import struct
from typing import Callable, Sequence, TypeVar

U8 = "<B"
U64 = "<Q"
BOOL = "<?"
OPTION_NONE = b"\x00"
OPTION_SOME = b"\x01"

T = TypeVar("T")


def u8(value: int) -> bytes:
    if not 0 <= value <= 0xFF:
        raise ValueError(f"u8 out of range: {value}")
    return struct.pack(U8, value)


def u64(value: int) -> bytes:
    if not 0 <= value <= 0xFFFF_FFFF_FFFF_FFFF:
        raise ValueError(f"u64 out of range: {value}")
    return struct.pack(U64, value)


def boolean(value: bool) -> bytes:
    return struct.pack(BOOL, value)


def fixed_bytes(value: bytes | bytearray, length: int) -> bytes:
    payload = bytes(value)
    if len(payload) != length:
        raise ValueError(f"expected {length} bytes, got {len(payload)}")
    return payload


def option(encoder: Callable[[T], bytes], value: T | None) -> bytes:
    if value is None:
        return OPTION_NONE
    return OPTION_SOME + encoder(value)


def instruction_discriminator(name: str) -> bytes:
    """Anchor's 8-byte discriminator for a program instruction."""

    return hashlib.sha256(f"global:{name}".encode()).digest()[:8]


def account_discriminator(name: str) -> bytes:
    """Anchor's 8-byte discriminator for an account type."""

    return hashlib.sha256(f"account:{name}".encode()).digest()[:8]


def event_discriminator(name: str) -> bytes:
    """Anchor's 8-byte discriminator for an emitted event."""

    return hashlib.sha256(f"event:{name}".encode()).digest()[:8]


def concat(chunks: Sequence[bytes]) -> bytes:
    return b"".join(chunks)
