import csv
import io
import secrets
from collections import defaultdict

from fastapi import APIRouter, Depends, File, Header, Query, Request, UploadFile
from pydantic import ValidationError
from sqlalchemy import select

from app.models import (
    AuditEvent,
    BankTransaction,
    FinancialException,
    Invoice,
    LedgerEntry,
    Proposal,
)
from app.schemas import ApplyRequest, ImportData, ReviewRequest
from app.services.approvals import review
from app.services.audit import audit
from app.services.importing import DomainError, import_data
from app.services.ledger import apply

router = APIRouter(prefix="/api")


def reviewer(request: Request, x_reviewer_token: str = Header(default="")):
    if not secrets.compare_digest(x_reviewer_token, request.app.state.settings.demo_reviewer_token):
        raise DomainError("Demo reviewer token required (simulated authentication)", 403)
    return "demo-reviewer"


@router.post("/proposals/{proposal_id}/review")
def review_proposal(
    proposal_id: str, body: ReviewRequest, request: Request, actor=Depends(reviewer)
):
    with request.app.state.db.session(write=True) as session:
        return review(session, proposal_id, body, actor, request.state.correlation_id)


@router.post("/proposals/{proposal_id}/apply")
def apply_proposal(
    proposal_id: str,
    body: ApplyRequest,
    request: Request,
    idempotency_key: str = Header(min_length=8, max_length=128),
    actor=Depends(reviewer),
):
    try:
        with request.app.state.db.session(write=True) as session:
            return apply(
                session,
                proposal_id,
                body.version,
                idempotency_key,
                actor,
                request.state.correlation_id,
            )
    except Exception as exc:
        # The attempted financial transaction rolls back before this separate failure record.
        with request.app.state.db.session(write=True) as session:
            audit(
                session,
                "ledger_writeback_failed",
                "proposal",
                proposal_id,
                actor=actor,
                reason=exc.message
                if isinstance(exc, DomainError)
                else "Posting failed; financial transaction rolled back",
                correlation_id=request.state.correlation_id,
            )
        raise


@router.get("/ledger")
def ledger(request: Request):
    with request.app.state.db.session() as session:
        return list(session.scalars(select(LedgerEntry).order_by(LedgerEntry.timestamp)))


@router.get("/audit")
def audit_history(
    request: Request,
    action: str | None = None,
    entity_id: str | None = None,
    limit: int = Query(default=200, ge=1, le=10000),
):
    with request.app.state.db.session() as session:
        query = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
        if action:
            query = query.where(AuditEvent.action == action)
        if entity_id:
            query = query.where(AuditEvent.entity_id == entity_id)
        return list(session.scalars(query))


@router.get("/overview")
def overview(request: Request):
    with request.app.state.db.session() as session:
        invoices = list(session.scalars(select(Invoice)))
        transactions = list(session.scalars(select(BankTransaction)))
        proposals = list(session.scalars(select(Proposal)))
        entries = list(session.scalars(select(LedgerEntry)))
        exceptions = list(session.scalars(select(FinancialException)))
        volume = defaultdict(int)
        reconciled = defaultdict(int)
        for t in transactions:
            volume[t.currency] += abs(t.amount_cents)
        for e in entries:
            reconciled[e.currency] += e.amount_cents
        paid = sum(i.status == "PAID" for i in invoices)
        return {
            "total_invoices": len(invoices),
            "total_transactions": len(transactions),
            "payment_volume": dict(volume),
            "reconciled_amount": dict(reconciled),
            "pending_approvals": sum(p.status == "PROPOSED" for p in proposals),
            "unresolved_exceptions": sum(e.status == "OPEN" for e in exceptions),
            "matching_rate": round(paid / len(invoices) * 100, 1) if invoices else 0,
            "status_counts": [
                {"name": s.title(), "count": sum(p.status == s for p in proposals)}
                for s in ("PROPOSED", "APPROVED", "APPLIED", "REJECTED")
            ],
        }


@router.post("/import/csv")
async def import_csv(
    request: Request,
    kind: str = Query(pattern="^(invoices|transactions)$"),
    file: UploadFile = File(),
):
    raw = await file.read(1_000_001)
    if len(raw) > 1_000_000:
        raise DomainError("CSV limit is 1 MB", 413)
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")), strict=True)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("Missing or duplicate CSV headers")
        rows = list(reader)
        for row in rows:
            if None in row or not row.get("amount_cents", "").lstrip("-").isdigit():
                raise ValueError("CSV amounts must be integer cents and rows must match headers")
            row["amount_cents"] = int(row["amount_cents"])
        data = ImportData.model_validate({kind: rows})
    except (UnicodeDecodeError, ValueError, ValidationError, csv.Error) as exc:
        raise DomainError(f"Invalid CSV: {str(exc)[:300]}", 422) from exc
    with request.app.state.db.session(write=True) as session:
        return import_data(session, data, request.state.correlation_id)


@router.post("/exceptions/{exception_id}/investigate")
def investigate_exception(exception_id: str, request: Request):
    from app.services.investigation import CompatibleProvider, investigate

    settings = request.app.state.settings
    provider = getattr(request.app.state, "investigation_provider", None)
    if provider is None and settings.llm_api_key:
        provider = CompatibleProvider(settings)
    return investigate(request.app.state.db, exception_id, request.state.correlation_id, provider)
