from sqlalchemy import select

from app.models import Allocation, BankTransaction, FinancialException, Invoice, Proposal
from app.services.audit import audit
from app.services.importing import DomainError
from app.services.matching import SAFE_METHODS, classify, digest


def reconcile(session, correlation_id):
    invoices = list(session.scalars(select(Invoice).order_by(Invoice.id)))
    transactions = list(session.scalars(select(BankTransaction).order_by(BankTransaction.id)))
    proposals = 0
    exceptions = 0
    covered = set()
    active_signatures = set()
    for invoice in invoices:
        if invoice.status == "PAID":
            continue
        evidence = classify(invoice, transactions, invoices)
        method = evidence["classification"]
        covered.update(evidence["transaction_ids"])
        signature = digest(evidence)
        if method in SAFE_METHODS:
            if not session.scalar(select(Proposal).where(Proposal.signature == signature)):
                proposal = Proposal(
                    signature=signature,
                    matching_method=method,
                    evidence=evidence,
                    proposed_amount_cents=invoice.amount_cents,
                    match_quality="high" if method == "reference_exact" else "review_required",
                )
                session.add(proposal)
                session.flush()
                for tx in evidence["transactions"]:
                    session.add(
                        Allocation(
                            proposal_id=proposal.id,
                            invoice_id=invoice.id,
                            transaction_id=tx["id"],
                            amount_cents=abs(tx["amount_cents"]),
                        )
                    )
                audit(
                    session,
                    "proposal_generated",
                    "proposal",
                    proposal.id,
                    after=evidence,
                    correlation_id=correlation_id,
                )
                proposals += 1
        if method not in {"reference_exact", "date_window"}:
            active_signatures.add(signature)
            existing = session.scalar(
                select(FinancialException).where(FinancialException.signature == signature)
            )
            if not existing:
                exception = FinancialException(
                    signature=signature,
                    invoice_id=invoice.id,
                    classification=method,
                    evidence=evidence,
                )
                session.add(exception)
                session.flush()
                audit(
                    session,
                    "exception_identified",
                    "exception",
                    exception.id,
                    after=evidence,
                    correlation_id=correlation_id,
                )
                exceptions += 1
            else:
                existing.status = "OPEN"
    for tx in transactions:
        if tx.status != "OPEN" or tx.id in covered:
            continue
        evidence = {
            "classification": "unmatched_transaction",
            "transaction_ids": [tx.id],
            "invoice_ids": [],
            "explanation": "No supported invoice evidence for this bank transaction.",
        }
        signature = digest(evidence)
        active_signatures.add(signature)
        if not session.scalar(
            select(FinancialException).where(FinancialException.signature == signature)
        ):
            exception = FinancialException(
                signature=signature,
                transaction_id=tx.id,
                classification="unmatched_transaction",
                evidence=evidence,
            )
            session.add(exception)
            session.flush()
            audit(
                session,
                "exception_identified",
                "exception",
                exception.id,
                after=evidence,
                correlation_id=correlation_id,
            )
            exceptions += 1
    for exception in session.scalars(select(FinancialException)):
        if exception.signature not in active_signatures:
            exception.status = "RESOLVED"
    result = {"new_proposals": proposals, "new_exceptions": exceptions}
    audit(
        session,
        "reconciliation_executed",
        "dataset",
        "all",
        after=result,
        correlation_id=correlation_id,
    )
    return result


def verify(session, proposal):
    if not proposal.allocations:
        raise DomainError("Proposal has no allocations")
    invoice_ids = {a.invoice_id for a in proposal.allocations}
    if len(invoice_ids) != 1:
        raise DomainError("Only one-invoice settlements are supported")
    invoice = session.get(Invoice, next(iter(invoice_ids)))
    if invoice.status != "OPEN":
        raise DomainError("Invoice is already settled")
    evidence = classify(
        invoice,
        list(session.scalars(select(BankTransaction))),
        list(session.scalars(select(Invoice))),
    )
    if evidence["classification"] not in SAFE_METHODS or digest(evidence) != proposal.signature:
        raise DomainError(
            "Stale or invalid evidence: run reconciliation and review current records"
        )
    amounts = {t["id"]: abs(t["amount_cents"]) for t in evidence["transactions"]}
    if (
        len(proposal.allocations) != len(amounts)
        or {a.transaction_id: a.amount_cents for a in proposal.allocations} != amounts
        or sum(a.amount_cents for a in proposal.allocations) != invoice.amount_cents
        or proposal.proposed_amount_cents != invoice.amount_cents
    ):
        raise DomainError("Allocation exceeds or differs from verified financial evidence")
    return evidence


def proposal_view(session, proposal):
    valid, error = False, None
    if proposal.status in {"PROPOSED", "APPROVED"}:
        try:
            verify(session, proposal)
            valid = True
        except DomainError as exc:
            error = exc.message
    return {
        "id": proposal.id,
        "invoice_ids": sorted({a.invoice_id for a in proposal.allocations}),
        "transaction_ids": [a.transaction_id for a in proposal.allocations],
        "matching_method": proposal.matching_method,
        "evidence": proposal.evidence,
        "proposed_amount_cents": proposal.proposed_amount_cents,
        "match_quality": proposal.match_quality,
        "status": proposal.status,
        "version": proposal.version,
        "created_at": proposal.created_at,
        "verification": {"valid": valid, "error": error},
    }
