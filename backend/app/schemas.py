"""Pydantic request/response models for the public API."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field, field_validator


class ChallengeRequest(BaseModel):
    wallet: str = Field(min_length=32, max_length=44)


class ChallengeResponse(BaseModel):
    wallet: str
    nonce: str
    message: str
    expires_at: dt.datetime


class VerifyRequest(BaseModel):
    wallet: str
    signature: str = Field(description="Base64 signature of the challenge message")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    wallet: str
    role: str


class EvidenceInfo(BaseModel):
    filename: str
    media_type: str
    size: int
    sha256: str


class ReportCreate(BaseModel):
    title: str = Field(min_length=4, max_length=200)
    summary: str = Field(min_length=10, max_length=1000)
    description: str = Field(min_length=20, max_length=20000)
    category: int = Field(ge=0, le=5)
    jurisdiction: str = Field(default="", max_length=120)
    entity_name: str = Field(default="", max_length=200)

    @field_validator("description")
    @classmethod
    def description_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("description must not be blank")
        return value


class ReportRead(BaseModel):
    id: int
    reporter_wallet: str
    title: str
    summary: str
    category: int
    category_label: str
    jurisdiction: str
    entity_name: str
    content_hash: str
    evidence_hash: str | None
    status: str
    on_chain_id: int | None
    submit_signature: str | None
    decision_signature: str | None
    reward_amount: int | None
    decision_note: str | None
    created_at: dt.datetime
    anchored_at: dt.datetime | None
    decided_at: dt.datetime | None

    model_config = {"from_attributes": True}


class ReportDetail(ReportRead):
    description: str
    evidence: EvidenceInfo | None = None


class PrepareSubmission(BaseModel):
    """An unsigned transaction the reporter's wallet must sign."""

    report_id: int
    on_chain_id: int
    transaction: str = Field(description="Base64-encoded unsigned VersionedTransaction")
    content_hash: str
    evidence_hash: str
    program_id: str


class ConfirmSubmission(BaseModel):
    signature: str


class DecisionRequest(BaseModel):
    reward_amount: int | None = Field(default=None, ge=0)
    note: str = Field(default="", max_length=2000)


class FundPoolRequest(BaseModel):
    amount: int = Field(gt=0, description="CORRUPT base units to transfer to the pool")


class ConfigUpdateRequest(BaseModel):
    verifier: str | None = None
    treasury: str | None = None
    min_reward: int | None = Field(default=None, gt=0)
    max_reward: int | None = Field(default=None, gt=0)


class PauseRequest(BaseModel):
    paused: bool


class ChainEventRead(BaseModel):
    id: int
    signature: str
    name: str
    payload: str
    slot: int | None
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class ConfigRead(BaseModel):
    authority: str
    verifier: str
    treasury: str
    reward_mint: str
    total_budget: int
    total_distributed: int
    remaining_budget: int
    report_count: int
    min_reward: int
    max_reward: int
    paused: bool
    created_at: int
    token_symbol: str = "CORRUPT"
    token_decimals: int = 6


class PlatformStats(BaseModel):
    total_reports: int
    pending: int
    verified: int
    rejected: int
    total_reward_paid: int
    unique_reporters: int


class AuditEventRead(BaseModel):
    id: int
    actor: str
    action: str
    report_id: int | None
    details: str
    created_at: dt.datetime

    model_config = {"from_attributes": True}
