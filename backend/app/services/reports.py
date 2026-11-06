"""Report lifecycle: draft, anchor on-chain, verify, reward.

The API never holds a reporter's private key. Anchoring is therefore split in
two steps: the backend builds an unsigned transaction and the reporter's
wallet signs it client-side before the signature is confirmed back to the
API. Reward payouts are signed by the verifier key held by the operator.
"""

from __future__ import annotations

import base64
import os
import secrets

from solders.message import Message
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.transaction import VersionedTransaction
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import AuditEvent, ChainEvent, Report, Wallet, utcnow
from app.services import evidence as evidence_service
from app.services.hashing import report_content_hash
from app.solana import CATEGORY_LABELS, SolanaClient, instructions, load_keypair
from app.solana.client import decode_events, deserialize_config


class ReportError(ValueError):
    """Raised when a report transition is not allowed."""


def record_audit(
    db: Session, actor: str, action: str, report_id: int | None, details: str
) -> None:
    db.add(AuditEvent(actor=actor, action=action, report_id=report_id, details=details))


def _program_id() -> Pubkey:
    return Pubkey.from_string(get_settings().program_id)


def _client() -> SolanaClient:
    settings = get_settings()
    return SolanaClient(settings.solana_rpc_url, settings.solana_commitment)


def _fetch_config(client: SolanaClient):
    account = client.get_account(instructions.config_pda(_program_id())[0])
    if account is None:
        raise ReportError("program is not initialized")
    return deserialize_config(account.data)


def _unsigned_transaction(message: Message) -> VersionedTransaction:
    """Wraps a message with empty signature slots so a wallet can fill them."""

    placeholders = [Signature.default()] * message.header.num_required_signatures
    return VersionedTransaction.populate(message, placeholders)


def _store_events(db: Session, signature: str, events: list[dict], slot: int | None) -> None:
    for event in events:
        db.add(
            ChainEvent(signature=signature, name=event["name"], payload=event["raw"], slot=slot)
        )


def create_report(
    db: Session,
    wallet: Wallet,
    *,
    title: str,
    summary: str,
    description: str,
    category: int,
    jurisdiction: str,
    entity_name: str,
) -> Report:
    content_hash = report_content_hash(
        title=title,
        summary=summary,
        description=description,
        category=category,
        jurisdiction=jurisdiction,
        entity_name=entity_name,
        reporter_wallet=wallet.address,
    )
    existing = db.execute(
        select(Report).where(Report.content_hash == content_hash)
    ).scalar_one_or_none()
    if existing is not None:
        raise ReportError("an identical report already exists")

    report = Report(
        reporter_id=wallet.id,
        reporter_wallet=wallet.address,
        title=title.strip(),
        summary=summary.strip(),
        description=description,
        category=category,
        jurisdiction=jurisdiction.strip(),
        entity_name=entity_name.strip(),
        content_hash=content_hash,
        status="draft",
    )
    db.add(report)
    db.flush()
    record_audit(db, wallet.address, "report.created", report.id, f"category={category}")
    return report


def attach_evidence(
    db: Session,
    report: Report,
    *,
    filename: str,
    media_type: str,
    payload: bytes,
) -> None:
    if report.status != "draft":
        raise ReportError("evidence can only be attached while the report is a draft")
    token = secrets.token_hex(8)
    stored = evidence_service.store_evidence(token, filename, media_type, payload)
    report.evidence_hash = stored.digest
    report.evidence_path = stored.path
    report.evidence_size = stored.size
    report.evidence_media_type = media_type
    db.flush()
    record_audit(
        db, report.reporter_wallet, "report.evidence_attached", report.id, stored.digest
    )


def build_submission_transaction(db: Session, report: Report) -> dict:
    """Builds the unsigned ``submit_report`` transaction for the reporter."""

    if report.status != "draft":
        raise ReportError("report has already been anchored")
    if not report.evidence_hash:
        raise ReportError("attach evidence before anchoring the report")

    program_id = _program_id()
    with _client() as client:
        config_state = _fetch_config(client)
        if config_state.paused:
            raise ReportError("program is paused")
        on_chain_id = config_state.report_count
        reporter = Pubkey.from_string(report.reporter_wallet)
        instruction = instructions.build_submit_report(
            program_id=program_id,
            reporter=reporter,
            content_hash=bytes.fromhex(report.content_hash),
            evidence_hash=bytes.fromhex(report.evidence_hash),
            category=report.category,
            report_id=on_chain_id,
        )
        message = Message.new_with_blockhash(
            [instruction], reporter, client.latest_blockhash()
        )
        unsigned = _unsigned_transaction(message)

    report.on_chain_id = on_chain_id
    report.status = "awaiting_signature"
    db.flush()
    return {
        "report_id": report.id,
        "on_chain_id": on_chain_id,
        "transaction": base64.b64encode(bytes(unsigned)).decode(),
        "content_hash": report.content_hash,
        "evidence_hash": report.evidence_hash,
        "program_id": str(program_id),
    }


def confirm_submission(db: Session, report: Report, signature: str) -> None:
    if report.status != "awaiting_signature":
        raise ReportError("report is not awaiting a signature")

    with _client() as client:
        if not client.confirm_signature(signature):
            raise ReportError("transaction was not confirmed")
        tx = client.get_transaction(signature) or {}
        meta = tx.get("meta") or {}
        if meta.get("err") is not None:
            raise ReportError(f"transaction failed: {meta['err']}")
        _store_events(db, signature, decode_events(meta.get("logMessages") or []), tx.get("slot"))

    report.status = "pending"
    report.submit_signature = signature
    report.anchored_at = utcnow()
    db.flush()
    record_audit(db, report.reporter_wallet, "report.anchored", report.id, signature)


def verifier_keypair():
    key_path = get_settings().verifier_keypair or os.environ.get("CORRUPT_VERIFIER_KEYPAIR")
    if not key_path:
        raise ReportError("verifier keypair is not configured")
    return load_keypair(key_path)


def authority_keypair():
    key_path = get_settings().authority_keypair or os.environ.get("CORRUPT_AUTHORITY_KEYPAIR")
    if not key_path:
        raise ReportError("authority keypair is not configured")
    return load_keypair(key_path)


def verify_report(
    db: Session,
    report: Report,
    *,
    reward_amount: int,
    note: str,
    actor: str,
) -> None:
    if report.status != "pending":
        raise ReportError("only pending reports can be verified")
    if report.on_chain_id is None:
        raise ReportError("report has no on-chain id")

    keypair = verifier_keypair()
    with _client() as client:
        config_state = _fetch_config(client)
        if not config_state.min_reward <= reward_amount <= config_state.max_reward:
            raise ReportError("reward is outside the configured bounds")
        if reward_amount > config_state.remaining_budget:
            raise ReportError("reward exceeds the remaining pool budget")

        instruction = instructions.build_verify_report(
            program_id=_program_id(),
            verifier=keypair.pubkey(),
            reporter=Pubkey.from_string(report.reporter_wallet),
            report_id=report.on_chain_id,
            reward_mint=Pubkey.from_string(config_state.reward_mint),
            treasury=Pubkey.from_string(config_state.treasury),
            reward_amount=reward_amount,
        )
        signature, events = client.sign_and_send([instruction], keypair)

    _store_events(db, signature, events, None)
    report.status = "verified"
    report.reward_amount = reward_amount
    report.decision_note = note
    report.decision_signature = signature
    report.decided_at = utcnow()
    db.flush()
    record_audit(db, actor, "report.verified", report.id, f"reward={reward_amount}")


def reject_report(db: Session, report: Report, *, note: str, actor: str) -> None:
    if report.status != "pending":
        raise ReportError("only pending reports can be rejected")
    if report.on_chain_id is None:
        raise ReportError("report has no on-chain id")

    keypair = verifier_keypair()
    with _client() as client:
        instruction = instructions.build_reject_report(
            program_id=_program_id(),
            verifier=keypair.pubkey(),
            report_id=report.on_chain_id,
        )
        signature, events = client.sign_and_send([instruction], keypair)

    _store_events(db, signature, events, None)
    report.status = "rejected"
    report.decision_note = note
    report.decision_signature = signature
    report.decided_at = utcnow()
    db.flush()
    record_audit(db, actor, "report.rejected", report.id, note)


def fund_pool(db: Session, actor: str, amount: int) -> dict:
    keypair = authority_keypair()
    with _client() as client:
        config_state = _fetch_config(client)
        instruction = instructions.build_fund_pool(
            program_id=_program_id(),
            funder=keypair.pubkey(),
            reward_mint=Pubkey.from_string(config_state.reward_mint),
            treasury=Pubkey.from_string(config_state.treasury),
            amount=amount,
        )
        signature, events = client.sign_and_send([instruction], keypair)

    _store_events(db, signature, events, None)
    record_audit(db, actor, "pool.funded", None, f"amount={amount}")
    return {"signature": signature, "amount": amount}


def set_paused(db: Session, actor: str, paused: bool) -> dict:
    keypair = authority_keypair()
    with _client() as client:
        instruction = instructions.build_set_paused(
            program_id=_program_id(), authority=keypair.pubkey(), paused=paused
        )
        signature, events = client.sign_and_send([instruction], keypair)

    _store_events(db, signature, events, None)
    record_audit(db, actor, "platform.pause_toggled", None, f"paused={paused}")
    return {"signature": signature, "paused": paused}


def platform_stats(db: Session) -> dict:
    total = db.execute(select(func.count(Report.id))).scalar_one()
    by_status = dict(
        db.execute(select(Report.status, func.count(Report.id)).group_by(Report.status)).all()
    )
    paid = db.execute(
        select(func.coalesce(func.sum(Report.reward_amount), 0)).where(
            Report.status == "verified"
        )
    ).scalar_one()
    reporters = db.execute(
        select(func.count(func.distinct(Report.reporter_wallet)))
    ).scalar_one()
    return {
        "total_reports": total,
        "pending": by_status.get("pending", 0),
        "verified": by_status.get("verified", 0),
        "rejected": by_status.get("rejected", 0),
        "total_reward_paid": int(paid),
        "unique_reporters": int(reporters),
    }


def report_timeline(report: Report) -> list[dict]:
    """Public, privacy-preserving timeline derived from report state."""

    timeline = [
        {
            "step": "created",
            "timestamp": report.created_at,
            "detail": "Report drafted off-chain",
        }
    ]
    if report.anchored_at:
        timeline.append(
            {
                "step": "anchored",
                "timestamp": report.anchored_at,
                "detail": f"Commitment anchored on-chain: {report.content_hash[:16]}…",
            }
        )
    if report.decided_at:
        timeline.append(
            {
                "step": report.status,
                "timestamp": report.decided_at,
                "detail": report.decision_note or "",
            }
        )
    return timeline


def to_read_model(report: Report) -> dict:
    return {
        "id": report.id,
        "reporter_wallet": report.reporter_wallet,
        "title": report.title,
        "summary": report.summary,
        "category": report.category,
        "category_label": CATEGORY_LABELS.get(report.category, "unknown"),
        "jurisdiction": report.jurisdiction,
        "entity_name": report.entity_name,
        "content_hash": report.content_hash,
        "evidence_hash": report.evidence_hash,
        "status": report.status,
        "on_chain_id": report.on_chain_id,
        "submit_signature": report.submit_signature,
        "decision_signature": report.decision_signature,
        "reward_amount": report.reward_amount,
        "decision_note": report.decision_note,
        "created_at": report.created_at,
        "anchored_at": report.anchored_at,
        "decided_at": report.decided_at,
    }
