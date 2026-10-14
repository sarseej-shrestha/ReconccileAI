from sqlalchemy import select

from app.models import (
    Approval,
    BankTransaction,
    FinancialException,
    IdempotencyRecord,
    Invoice,
    LedgerEntry,
    PostingOperation,
    Proposal,
)
from app.services.audit import audit
from app.services.importing import DomainError
from app.services.matching import digest
from app.services.reconciliation import verify


def posting_result(session, operation):
    entries = list(
        session.scalars(
            select(LedgerEntry)
            .where(LedgerEntry.operation_id == operation.id)
            .order_by(LedgerEntry.transaction_id)
        )
    )
    return {
        "operation_id": operation.id,
        "proposal_id": operation.proposal_id,
        "ledger_entries": [
            {
                "id": e.id,
                "invoice_id": e.invoice_id,
                "transaction_id": e.transaction_id,
                "amount_cents": e.amount_cents,
                "currency": e.currency,
                "entry_type": e.entry_type,
            }
            for e in entries
        ],
    }


def apply(session, proposal_id, version, key, reviewer, correlation_id):
    fingerprint = digest({"proposal_id": proposal_id, "version": version, "operation": "apply"})
    record = session.get(IdempotencyRecord, key)
    if record:
        if record.request_fingerprint != fingerprint:
            raise DomainError("Idempotency key already belongs to a different request")
        audit(
            session,
            "idempotent_retry",
            "proposal",
            proposal_id,
            actor=reviewer,
            after=record.result,
            reason="Stored result returned; no new ledger effects",
            correlation_id=correlation_id,
        )
        return {**record.result, "replayed": True, "additional_entries": 0}
    proposal = session.get(Proposal, proposal_id)
    if not proposal:
        raise DomainError("Proposal not found", 404)
    operation = session.scalar(
        select(PostingOperation).where(PostingOperation.proposal_id == proposal_id)
    )
    if operation:
        result = posting_result(session, operation)
        session.add(
            IdempotencyRecord(
                key=key,
                operation_type="apply",
                request_fingerprint=fingerprint,
                status="COMPLETED",
                result=result,
            )
        )
        audit(
            session,
            "idempotent_retry",
            "proposal",
            proposal_id,
            actor=reviewer,
            after=result,
            reason="Proposal was already applied under another key",
            correlation_id=correlation_id,
        )
        return {**result, "replayed": True, "additional_entries": 0}
    if proposal.status != "APPROVED" or proposal.version != version:
        raise DomainError("Only a currently approved proposal version can be applied")
    approval = session.scalar(select(Approval).where(Approval.proposal_id == proposal_id))
    if not approval or approval.decision != "APPROVED":
        raise DomainError("Missing human approval provenance")
    evidence = verify(session, proposal)
    audit(
        session,
        "ledger_writeback_initiated",
        "proposal",
        proposal_id,
        actor=reviewer,
        before={"status": proposal.status, "version": proposal.version},
        correlation_id=correlation_id,
    )
    operation = PostingOperation(proposal_id=proposal_id)
    session.add(operation)
    session.flush()
    for allocation in proposal.allocations:
        invoice = session.get(Invoice, allocation.invoice_id)
        tx = session.get(BankTransaction, allocation.transaction_id)
        session.add(
            LedgerEntry(
                invoice_id=invoice.id,
                transaction_id=tx.id,
                amount_cents=allocation.amount_cents,
                currency=invoice.currency,
                entry_type="receipt" if invoice.kind == "receivable" else "payment",
                operation_id=operation.id,
            )
        )
        tx.status = "POSTED"
        invoice.status = "PAID"
    proposal.status = "APPLIED"
    proposal.version += 1
    for exc in session.scalars(
        select(FinancialException).where(FinancialException.invoice_id.in_(evidence["invoice_ids"]))
    ):
        exc.status = "RESOLVED"
    session.flush()
    result = posting_result(session, operation)
    session.add(
        IdempotencyRecord(
            key=key,
            operation_type="apply",
            request_fingerprint=fingerprint,
            status="COMPLETED",
            result=result,
        )
    )
    audit(
        session,
        "ledger_writeback_completed",
        "proposal",
        proposal_id,
        actor=reviewer,
        before={"status": "APPROVED", "version": version},
        after={**result, "status": "APPLIED", "version": proposal.version},
        reason="Verified allocations settled atomically",
        correlation_id=correlation_id,
    )
    return {**result, "replayed": False, "additional_entries": len(result["ledger_entries"])}
