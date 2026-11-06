"""Deterministic hashing used to anchor reports on-chain.

The content hash must be reproducible by anyone holding the report body, so
the canonical form is defined here explicitly rather than relying on JSON
library defaults.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_bytes(payload: bytes) -> bytes:
    return hashlib.sha256(payload).digest()


def canonical_json(document: Mapping[str, Any]) -> bytes:
    """Serializes a mapping with sorted keys and no insignificant whitespace."""

    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def report_content_hash(
    *,
    title: str,
    summary: str,
    description: str,
    category: int,
    jurisdiction: str,
    entity_name: str,
    reporter_wallet: str,
) -> str:
    """Computes the on-chain content commitment for a report."""

    document = {
        "version": 1,
        "title": title.strip(),
        "summary": summary.strip(),
        "description": description.strip(),
        "category": category,
        "jurisdiction": jurisdiction.strip(),
        "entity_name": entity_name.strip(),
        "reporter_wallet": reporter_wallet,
    }
    return sha256_hex(canonical_json(document))
