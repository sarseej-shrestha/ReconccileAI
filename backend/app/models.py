from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def now():
    return datetime.now(UTC)


def uid():
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint("amount_cents > 0"),
        CheckConstraint("kind IN ('receivable', 'payable')"),
        CheckConstraint("status IN ('OPEN', 'PAID')"),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String, unique=True)
    counterparty: Mapped[str]
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    issue_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(default="receivable")
    status: Mapped[str] = mapped_column(default="OPEN", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class BankTransaction(Base):
    __tablename__ = "bank_transactions"
    __table_args__ = (
        CheckConstraint("amount_cents != 0"),
        CheckConstraint("status IN ('OPEN', 'POSTED')"),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True)
    external_reference: Mapped[str] = mapped_column(unique=True)
    counterparty: Mapped[str] = mapped_column(index=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    date: Mapped[date] = mapped_column(Date)
    description: Mapped[str]
    source: Mapped[str]
    status: Mapped[str] = mapped_column(default="OPEN", index=True)


class Proposal(Base):
    __tablename__ = "proposals"
    __table_args__ = (CheckConstraint("status IN ('PROPOSED', 'APPROVED', 'REJECTED', 'APPLIED')"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    signature: Mapped[str] = mapped_column(unique=True)
    matching_method: Mapped[str]
    evidence: Mapped[dict] = mapped_column(JSON)
    proposed_amount_cents: Mapped[int]
    match_quality: Mapped[str]
    status: Mapped[str] = mapped_column(default="PROPOSED", index=True)
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    allocations: Mapped[list["Allocation"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class Allocation(Base):
    __tablename__ = "allocations"
    __table_args__ = (
        UniqueConstraint("proposal_id", "transaction_id"),
        CheckConstraint("amount_cents > 0"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), index=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), index=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("bank_transactions.id"), index=True)
    amount_cents: Mapped[int]


class FinancialException(Base):
    __tablename__ = "exceptions"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    signature: Mapped[str] = mapped_column(unique=True)
    invoice_id: Mapped[str | None] = mapped_column(ForeignKey("invoices.id"), index=True)
    transaction_id: Mapped[str | None] = mapped_column(ForeignKey("bank_transactions.id"))
    classification: Mapped[str] = mapped_column(index=True)
    evidence: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Approval(Base):
    __tablename__ = "approvals"
    __table_args__ = (CheckConstraint("decision IN ('APPROVED', 'REJECTED')"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), unique=True)
    reviewer: Mapped[str]
    decision: Mapped[str]
    reason: Mapped[str]
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PostingOperation(Base):
    __tablename__ = "posting_operations"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (CheckConstraint("amount_cents > 0"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), index=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("bank_transactions.id"), unique=True)
    amount_cents: Mapped[int]
    currency: Mapped[str]
    entry_type: Mapped[str]
    operation_id: Mapped[str] = mapped_column(ForeignKey("posting_operations.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    key: Mapped[str] = mapped_column(primary_key=True)
    operation_type: Mapped[str]
    request_fingerprint: Mapped[str]
    status: Mapped[str]
    result: Mapped[dict] = mapped_column(JSON)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    actor: Mapped[str]
    action: Mapped[str] = mapped_column(index=True)
    entity_type: Mapped[str]
    entity_id: Mapped[str] = mapped_column(index=True)
    previous_state: Mapped[dict | None] = mapped_column(JSON)
    new_state: Mapped[dict | None] = mapped_column(JSON)
    reason: Mapped[str]
    correlation_id: Mapped[str] = mapped_column(index=True)
