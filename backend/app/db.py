"""Database engine, session factory and ORM models."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Wallet(Base):
    """A wallet that authenticated through a signed challenge."""

    __tablename__ = "wallets"

    id: Mapped[int] = mapped_column(primary_key=True)
    address: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(16), default="reporter")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    reports: Mapped[list["Report"]] = relationship(back_populates="reporter")


class AuthChallenge(Base):
    """A single-use nonce issued for wallet authentication."""

    __tablename__ = "auth_challenges"

    id: Mapped[int] = mapped_column(primary_key=True)
    wallet: Mapped[str] = mapped_column(String(64), index=True)
    nonce: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    message: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Report(Base):
    """Off-chain report metadata anchored on-chain by hash."""

    __tablename__ = "reports"
    __table_args__ = (UniqueConstraint("content_hash", name="uq_reports_content_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("wallets.id"), index=True)
    reporter_wallet: Mapped[str] = mapped_column(String(64), index=True)

    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[int] = mapped_column(Integer)
    jurisdiction: Mapped[str] = mapped_column(String(120), default="")
    entity_name: Mapped[str] = mapped_column(String(200), default="")

    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    evidence_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    evidence_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_media_type: Mapped[str | None] = mapped_column(String(120), nullable=True)

    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    on_chain_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    submit_signature: Mapped[str | None] = mapped_column(String(120), nullable=True)
    decision_signature: Mapped[str | None] = mapped_column(String(120), nullable=True)

    reward_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    anchored_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    reporter: Mapped[Wallet] = relationship(back_populates="reports")


class AuditEvent(Base):
    """Append-only audit trail of privileged actions."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    report_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ChainEvent(Base):
    """Mirror of on-chain program events for the transparency ledger."""

    __tablename__ = "chain_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    signature: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(48), index=True)
    payload: Mapped[str] = mapped_column(Text)
    slot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Paused(Base):
    """Singleton row mirroring the program pause flag for the API layer."""

    __tablename__ = "platform_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


_engine: Any = None
_SessionLocal: sessionmaker | None = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        connect_args = (
            {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
        )
        _engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return _SessionLocal


def init_db() -> None:
    Base.metadata.create_all(bind=get_engine())


def get_db() -> Iterator[Any]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_state() -> None:
    """Drop cached engine/session factory. Used by tests."""

    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None
