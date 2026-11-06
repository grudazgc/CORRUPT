"""HTTP API for the CORRUPT anti-corruption platform."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.config import get_settings
from app.db import AuditEvent, ChainEvent, Report, Wallet, get_db
from app.services import auth, reports
from app.services.evidence import EvidenceError
from app.solana import CATEGORY_LABELS, SolanaClient, instructions
from app.solana.client import deserialize_config

router = APIRouter(prefix="/api")

# Fields that must never be exposed publicly, because they can identify the
# whistleblower or the accused party.
PRIVATE_FIELDS = {"title", "description", "jurisdiction", "entity_name", "summary"}


def _public_report(report: Report) -> dict:
    """Strips identifying content from a report for public consumption."""

    model = reports.to_read_model(report)
    return {
        "id": model["id"],
        "category": model["category"],
        "category_label": model["category_label"],
        "content_hash": model["content_hash"],
        "evidence_hash": model["evidence_hash"],
        "status": model["status"],
        "on_chain_id": model["on_chain_id"],
        "reward_amount": model["reward_amount"],
        "created_at": model["created_at"],
        "anchored_at": model["anchored_at"],
        "decided_at": model["decided_at"],
    }


def _get_report(db: Session, report_id: int) -> Report:
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found")
    return report


def _on_chain_config():
    settings = get_settings()
    from solders.pubkey import Pubkey

    with SolanaClient(settings.solana_rpc_url, settings.solana_commitment) as client:
        account = client.get_account(instructions.config_pda(Pubkey.from_string(settings.program_id))[0])
    if account is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "program is not initialized")
    return deserialize_config(account.data)


# --------------------------------------------------------------------------- #
# Authentication
# --------------------------------------------------------------------------- #


@router.post("/auth/challenge", response_model=schemas.ChallengeResponse, tags=["auth"])
def request_challenge(payload: schemas.ChallengeRequest, db: Session = Depends(get_db)):
    challenge = auth.create_challenge(db, payload.wallet)
    return schemas.ChallengeResponse(
        wallet=challenge.wallet,
        nonce=challenge.nonce,
        message=challenge.message,
        expires_at=challenge.expires_at,
    )


@router.post("/auth/verify", response_model=schemas.TokenResponse, tags=["auth"])
def verify_challenge(payload: schemas.VerifyRequest, db: Session = Depends(get_db)):
    auth.consume_challenge(db, payload.wallet, payload.signature)
    wallet = auth.get_or_create_wallet(db, payload.wallet)
    token, expires_in = auth.issue_token(wallet)
    return schemas.TokenResponse(
        access_token=token, expires_in=expires_in, wallet=wallet.address, role=wallet.role
    )


@router.get("/auth/me", tags=["auth"])
def me(wallet: Wallet = Depends(auth.current_wallet)):
    return {"wallet": wallet.address, "role": wallet.role, "created_at": wallet.created_at}


# --------------------------------------------------------------------------- #
# Reports (reporter-facing)
# --------------------------------------------------------------------------- #


@router.post(
    "/reports", response_model=schemas.ReportRead, status_code=status.HTTP_201_CREATED, tags=["reports"]
)
def create_report(
    payload: schemas.ReportCreate,
    wallet: Wallet = Depends(auth.current_wallet),
    db: Session = Depends(get_db),
):
    try:
        report = reports.create_report(
            db,
            wallet,
            title=payload.title,
            summary=payload.summary,
            description=payload.description,
            category=payload.category,
            jurisdiction=payload.jurisdiction,
            entity_name=payload.entity_name,
        )
    except reports.ReportError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return reports.to_read_model(report)


@router.post("/reports/{report_id}/evidence", tags=["reports"])
async def upload_evidence(
    report_id: int,
    file: UploadFile = File(...),
    wallet: Wallet = Depends(auth.current_wallet),
    db: Session = Depends(get_db),
):
    report = _get_report(db, report_id)
    if report.reporter_wallet != wallet.address:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your report")
    payload = await file.read()
    try:
        reports.attach_evidence(
            db,
            report,
            filename=file.filename or "evidence.bin",
            media_type=file.content_type or "application/octet-stream",
            payload=payload,
        )
    except EvidenceError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except reports.ReportError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return {
        "report_id": report.id,
        "evidence_hash": report.evidence_hash,
        "size": report.evidence_size,
        "media_type": report.evidence_media_type,
    }


@router.post("/reports/{report_id}/prepare", response_model=schemas.PrepareSubmission, tags=["reports"])
def prepare_submission(
    report_id: int,
    wallet: Wallet = Depends(auth.current_wallet),
    db: Session = Depends(get_db),
):
    report = _get_report(db, report_id)
    if report.reporter_wallet != wallet.address:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your report")
    try:
        return reports.build_submission_transaction(db, report)
    except reports.ReportError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post("/reports/{report_id}/confirm", response_model=schemas.ReportRead, tags=["reports"])
def confirm_submission(
    report_id: int,
    payload: schemas.ConfirmSubmission,
    wallet: Wallet = Depends(auth.current_wallet),
    db: Session = Depends(get_db),
):
    report = _get_report(db, report_id)
    if report.reporter_wallet != wallet.address:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your report")
    try:
        reports.confirm_submission(db, report, payload.signature)
    except reports.ReportError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return reports.to_read_model(report)


@router.get("/reports/mine", response_model=list[schemas.ReportRead], tags=["reports"])
def my_reports(
    wallet: Wallet = Depends(auth.current_wallet), db: Session = Depends(get_db)
):
    rows = (
        db.execute(
            select(Report)
            .where(Report.reporter_wallet == wallet.address)
            .order_by(Report.id.desc())
        )
        .scalars()
        .all()
    )
    return [reports.to_read_model(row) for row in rows]


@router.get("/reports/{report_id}", tags=["reports"])
def get_report(
    report_id: int,
    wallet: Wallet = Depends(auth.current_wallet),
    db: Session = Depends(get_db),
):
    report = _get_report(db, report_id)
    if report.reporter_wallet != wallet.address:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your report")
    detail = reports.to_read_model(report)
    detail["description"] = report.description
    detail["evidence"] = (
        {
            "filename": (report.evidence_path or "").rsplit("/", 1)[-1],
            "media_type": report.evidence_media_type or "",
            "size": report.evidence_size or 0,
            "sha256": report.evidence_hash or "",
        }
        if report.evidence_hash
        else None
    )
    detail["timeline"] = reports.report_timeline(report)
    return detail


# --------------------------------------------------------------------------- #
# Public transparency endpoints
# --------------------------------------------------------------------------- #


@router.get("/public/reports", tags=["public"])
def public_reports(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
):
    query = select(Report).order_by(Report.id.desc()).limit(limit).offset(offset)
    if status_filter:
        query = query.where(Report.status == status_filter)
    rows = db.execute(query).scalars().all()
    return [_public_report(row) for row in rows]


@router.get("/public/reports/{report_id}", tags=["public"])
def public_report(report_id: int, db: Session = Depends(get_db)):
    report = _get_report(db, report_id)
    return _public_report(report)


@router.get("/public/stats", response_model=schemas.PlatformStats, tags=["public"])
def public_stats(db: Session = Depends(get_db)):
    return reports.platform_stats(db)


@router.get("/public/ledger", response_model=list[schemas.ChainEventRead], tags=["public"])
def public_ledger(
    limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db)
):
    rows = (
        db.execute(select(ChainEvent).order_by(ChainEvent.id.desc()).limit(limit))
        .scalars()
        .all()
    )
    return rows


@router.get("/public/config", response_model=schemas.ConfigRead, tags=["public"])
def public_config():
    config = _on_chain_config()
    return schemas.ConfigRead(
        authority=config.authority,
        verifier=config.verifier,
        treasury=config.treasury,
        reward_mint=config.reward_mint,
        total_budget=config.total_budget,
        total_distributed=config.total_distributed,
        remaining_budget=config.remaining_budget,
        report_count=config.report_count,
        min_reward=config.min_reward,
        max_reward=config.max_reward,
        paused=config.paused,
        created_at=config.created_at,
    )


@router.get("/public/categories", tags=["public"])
def categories():
    return [{"id": key, "label": value} for key, value in CATEGORY_LABELS.items()]


# --------------------------------------------------------------------------- #
# Verifier endpoints
# --------------------------------------------------------------------------- #


@router.get("/verifier/queue", response_model=list[schemas.ReportDetail], tags=["verifier"])
def verifier_queue(
    _: None = Depends(auth.require_verifier), db: Session = Depends(get_db)
):
    rows = (
        db.execute(
            select(Report).where(Report.status == "pending").order_by(Report.id.asc())
        )
        .scalars()
        .all()
    )
    result = []
    for row in rows:
        detail = reports.to_read_model(row)
        detail["description"] = row.description
        detail["evidence"] = (
            {
                "filename": (row.evidence_path or "").rsplit("/", 1)[-1],
                "media_type": row.evidence_media_type or "",
                "size": row.evidence_size or 0,
                "sha256": row.evidence_hash or "",
            }
            if row.evidence_hash
            else None
        )
        result.append(detail)
    return result


@router.post("/verifier/reports/{report_id}/verify", tags=["verifier"])
def verify_report(
    report_id: int,
    payload: schemas.DecisionRequest,
    _: None = Depends(auth.require_verifier),
    db: Session = Depends(get_db),
):
    if payload.reward_amount is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "reward_amount is required")
    report = _get_report(db, report_id)
    try:
        reports.verify_report(
            db,
            report,
            reward_amount=payload.reward_amount,
            note=payload.note,
            actor="verifier",
        )
    except reports.ReportError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return reports.to_read_model(report)


@router.post("/verifier/reports/{report_id}/reject", tags=["verifier"])
def reject_report(
    report_id: int,
    payload: schemas.DecisionRequest,
    _: None = Depends(auth.require_verifier),
    db: Session = Depends(get_db),
):
    report = _get_report(db, report_id)
    try:
        reports.reject_report(db, report, note=payload.note, actor="verifier")
    except reports.ReportError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return reports.to_read_model(report)


# --------------------------------------------------------------------------- #
# Admin endpoints
# --------------------------------------------------------------------------- #


@router.post("/admin/pool/fund", tags=["admin"])
def fund_pool(
    payload: schemas.FundPoolRequest,
    _: None = Depends(auth.require_admin),
    db: Session = Depends(get_db),
):
    try:
        return reports.fund_pool(db, "admin", payload.amount)
    except reports.ReportError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post("/admin/pause", tags=["admin"])
def toggle_pause(
    payload: schemas.PauseRequest,
    _: None = Depends(auth.require_admin),
    db: Session = Depends(get_db),
):
    try:
        return reports.set_paused(db, "admin", payload.paused)
    except reports.ReportError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.get("/admin/audit", response_model=list[schemas.AuditEventRead], tags=["admin"])
def audit_log(
    limit: int = Query(default=100, ge=1, le=500),
    _: None = Depends(auth.require_admin),
    db: Session = Depends(get_db),
):
    return (
        db.execute(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit))
        .scalars()
        .all()
    )
