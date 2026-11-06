"""JSON-RPC client and account decoders for the corrupt_rewards program."""

from __future__ import annotations

import base64
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import httpx
from solders.hash import Hash
from solders.instruction import Instruction
from solders.keypair import Keypair
from solders.message import Message
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction

from app.solana import borsh

LAMPORTS_PER_SOL = 1_000_000_000


class SolanaError(RuntimeError):
    """Raised when the RPC node rejects a request or a transaction fails."""


@dataclass(frozen=True)
class AccountSnapshot:
    owner: str
    lamports: int
    data: bytes
    executable: bool


@dataclass(frozen=True)
class ConfigAccount:
    authority: str
    verifier: str
    treasury: str
    reward_mint: str
    total_budget: int
    total_distributed: int
    report_count: int
    min_reward: int
    max_reward: int
    paused: bool
    bump: int
    created_at: int

    @property
    def remaining_budget(self) -> int:
        return max(self.total_budget - self.total_distributed, 0)


@dataclass(frozen=True)
class ReportAccount:
    id: int
    reporter: str
    content_hash: str
    evidence_hash: str
    category: int
    status: int
    reward_amount: int
    submitted_at: int
    reviewed_at: int
    bump: int


STATUS_LABELS = {0: "pending", 1: "verified", 2: "rejected"}
CATEGORY_LABELS = {
    0: "bribery",
    1: "embezzlement",
    2: "procurement_fraud",
    3: "nepotism",
    4: "abuse_of_office",
    5: "other",
}


def load_keypair(path: str | Path) -> Keypair:
    """Loads a Solana CLI keypair JSON file."""

    raw = json.loads(Path(path).expanduser().read_text())
    return Keypair.from_bytes(bytes(raw))


def _read_u64(data: bytes, offset: int) -> tuple[int, int]:
    return struct.unpack_from("<Q", data, offset)[0], offset + 8


def _read_i64(data: bytes, offset: int) -> tuple[int, int]:
    return struct.unpack_from("<q", data, offset)[0], offset + 8


def _read_pubkey(data: bytes, offset: int) -> tuple[str, int]:
    return str(Pubkey.from_bytes(data[offset : offset + 32])), offset + 32


def deserialize_config(data: bytes) -> ConfigAccount:
    expected = borsh.account_discriminator("Config")
    if data[:8] != expected:
        raise SolanaError("account is not a Config account")
    offset = 8
    authority, offset = _read_pubkey(data, offset)
    verifier, offset = _read_pubkey(data, offset)
    treasury, offset = _read_pubkey(data, offset)
    reward_mint, offset = _read_pubkey(data, offset)
    total_budget, offset = _read_u64(data, offset)
    total_distributed, offset = _read_u64(data, offset)
    report_count, offset = _read_u64(data, offset)
    min_reward, offset = _read_u64(data, offset)
    max_reward, offset = _read_u64(data, offset)
    paused = bool(data[offset])
    offset += 1
    bump = data[offset]
    offset += 1
    created_at, offset = _read_i64(data, offset)
    return ConfigAccount(
        authority=authority,
        verifier=verifier,
        treasury=treasury,
        reward_mint=reward_mint,
        total_budget=total_budget,
        total_distributed=total_distributed,
        report_count=report_count,
        min_reward=min_reward,
        max_reward=max_reward,
        paused=paused,
        bump=bump,
        created_at=created_at,
    )


def deserialize_report(data: bytes) -> ReportAccount:
    expected = borsh.account_discriminator("Report")
    if data[:8] != expected:
        raise SolanaError("account is not a Report account")
    offset = 8
    report_id, offset = _read_u64(data, offset)
    reporter, offset = _read_pubkey(data, offset)
    content_hash = data[offset : offset + 32].hex()
    offset += 32
    evidence_hash = data[offset : offset + 32].hex()
    offset += 32
    category = data[offset]
    offset += 1
    status = data[offset]
    offset += 1
    reward_amount, offset = _read_u64(data, offset)
    submitted_at, offset = _read_i64(data, offset)
    reviewed_at, offset = _read_i64(data, offset)
    bump = data[offset]
    return ReportAccount(
        id=report_id,
        reporter=reporter,
        content_hash=content_hash,
        evidence_hash=evidence_hash,
        category=category,
        status=status,
        reward_amount=reward_amount,
        submitted_at=submitted_at,
        reviewed_at=reviewed_at,
        bump=bump,
    )


def decode_events(logs: Sequence[str]) -> list[dict[str, Any]]:
    """Decodes Anchor events from a transaction's log messages."""

    known = {
        "ConfigInitialized": ("config_initialized", 32 + 32 + 32 + 32 + 8 + 8 + 8),
        "ReportSubmitted": ("report_submitted", 8 + 32 + 1 + 32 + 32 + 8),
        "ReportVerified": ("report_verified", 8 + 32 + 32 + 8 + 8),
        "ReportRejected": ("report_rejected", 8 + 32 + 32 + 8),
        "RewardPoolFunded": ("reward_pool_funded", 32 + 8 + 8 + 8),
        "ConfigUpdated": ("config_updated", 32 + 32 + 32 + 8 + 8 + 8),
        "PauseToggled": ("pause_toggled", 1 + 8),
    }
    events: list[dict[str, Any]] = []
    for line in logs:
        if "Program data: " not in line:
            continue
        payload_b64 = line.split("Program data: ", 1)[1].strip()
        try:
            payload = base64.b64decode(payload_b64)
        except (ValueError, TypeError):
            continue
        for event_name, (label, _size) in known.items():
            if payload[:8] == borsh.event_discriminator(event_name):
                events.append(
                    {
                        "name": label,
                        "raw": payload[8:].hex(),
                    }
                )
                break
    return events


class SolanaClient:
    """Thin JSON-RPC wrapper covering the calls this platform needs."""

    def __init__(
        self,
        rpc_url: str,
        commitment: str = "confirmed",
        timeout: float = 30.0,
    ) -> None:
        self.rpc_url = rpc_url
        self.commitment = commitment
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SolanaClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _call(self, method: str, params: list[Any] | None = None) -> Any:
        body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
        response = self._client.post(self.rpc_url, json=body)
        response.raise_for_status()
        payload = response.json()
        if "error" in payload:
            raise SolanaError(f"{method} failed: {payload['error']}")
        return payload.get("result")

    def latest_blockhash(self) -> Hash:
        result = self._call("getLatestBlockhash", [{"commitment": self.commitment}])
        return Hash.from_string(result["value"]["blockhash"])

    def get_account(self, pubkey: Pubkey) -> AccountSnapshot | None:
        result = self._call(
            "getAccountInfo",
            [str(pubkey), {"encoding": "base64", "commitment": self.commitment}],
        )
        value = result.get("value")
        if value is None:
            return None
        data = base64.b64decode(value["data"][0])
        return AccountSnapshot(
            owner=value["owner"],
            lamports=value["lamports"],
            data=data,
            executable=value["executable"],
        )

    def get_balance(self, pubkey: Pubkey) -> int:
        result = self._call("getBalance", [str(pubkey), {"commitment": self.commitment}])
        return int(result["value"])

    def request_airdrop(self, pubkey: Pubkey, lamports: int) -> str:
        return str(self._call("requestAirdrop", [str(pubkey), lamports]))

    def send_transaction(self, transaction: VersionedTransaction) -> str:
        encoded = base64.b64encode(bytes(transaction)).decode()
        result = self._call(
            "sendTransaction",
            [
                encoded,
                {"encoding": "base64", "skipPreflight": False, "preflightCommitment": self.commitment},
            ],
        )
        return str(result)

    def get_transaction(self, signature: str) -> dict[str, Any] | None:
        result = self._call(
            "getTransaction",
            [
                signature,
                {
                    "encoding": "json",
                    "commitment": self.commitment,
                    "maxSupportedTransactionVersion": 0,
                },
            ],
        )
        return result

    def confirm_signature(self, signature: str, attempts: int = 30, delay: float = 0.5) -> bool:
        import time

        for _ in range(attempts):
            tx = self.get_transaction(signature)
            if tx is not None:
                if tx.get("meta", {}).get("err") is not None:
                    raise SolanaError(f"transaction {signature} failed: {tx['meta']['err']}")
                return True
            time.sleep(delay)
        return False

    def build_transaction(
        self, instructions: Sequence[Instruction], payer: Keypair
    ) -> VersionedTransaction:
        blockhash = self.latest_blockhash()
        message = Message.new_with_blockhash(list(instructions), payer.pubkey(), blockhash)
        return VersionedTransaction(message, [payer])

    def sign_and_send(
        self, instructions: Sequence[Instruction], payer: Keypair
    ) -> tuple[str, list[dict[str, Any]]]:
        transaction = self.build_transaction(instructions, payer)
        signature = self.send_transaction(transaction)
        self.confirm_signature(signature)
        tx = self.get_transaction(signature) or {}
        logs = (tx.get("meta") or {}).get("logMessages") or []
        return signature, decode_events(logs)
