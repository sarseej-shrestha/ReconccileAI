"""Conservative rules. No financial state changes; every result includes concrete evidence."""

import hashlib
import json
import re
from collections import Counter
from datetime import timedelta

from app.models import BankTransaction, Invoice

SAFE_METHODS = {"reference_exact", "date_window", "split_payment"}


def normalize(value):
    return re.sub(r"[^a-z0-9]", "", value.lower())


def references(transaction):
    return set(re.findall(r"\bINV-[A-Z0-9]+\b", transaction.description.upper()))


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def invoice_snapshot(invoice):
    return {
        k: str(getattr(invoice, k)) if k.endswith("date") else getattr(invoice, k)
        for k in (
            "id",
            "invoice_number",
            "counterparty",
            "amount_cents",
            "currency",
            "issue_date",
            "due_date",
            "kind",
        )
    }


def transaction_snapshot(tx):
    return {
        k: str(getattr(tx, k)) if k == "date" else getattr(tx, k)
        for k in (
            "id",
            "external_reference",
            "counterparty",
            "amount_cents",
            "currency",
            "date",
            "description",
            "source",
        )
    }


def in_window(invoice, tx):
    return (
        invoice.issue_date - timedelta(days=7) <= tx.date <= invoice.due_date + timedelta(days=30)
    )


def right_direction(invoice, tx):
    return tx.amount_cents > 0 if invoice.kind == "receivable" else tx.amount_cents < 0


def duplicate_ids(transactions):
    def key(tx):
        return (
            normalize(tx.counterparty),
            tx.amount_cents,
            tx.currency,
            tx.date,
            tuple(sorted(references(tx))),
        )

    counts = Counter(key(tx) for tx in transactions)
    return {tx.id for tx in transactions if counts[key(tx)] > 1}


def classify(invoice: Invoice, transactions: list[BankTransaction], invoices: list[Invoice]):
    available = [t for t in transactions if t.status == "OPEN"]
    direct = [t for t in available if invoice.invoice_number in references(t)]
    candidates = direct or [
        t for t in available if normalize(t.counterparty) == normalize(invoice.counterparty)
    ]
    candidates.sort(key=lambda t: t.id)
    duplicates = duplicate_ids(available)
    classification = "missing_payment"
    if candidates:
        if any(len(references(t)) > 1 for t in candidates):
            classification = "conflicting_references"
        elif any(references(t) and references(t) != {invoice.invoice_number} for t in candidates):
            classification = "unsupported_reference"
        elif any(t.currency != invoice.currency for t in candidates):
            classification = "cross_currency"
        elif any(not right_direction(invoice, t) for t in candidates):
            classification = "payment_direction"
        elif any(t.id in duplicates for t in candidates):
            classification = "duplicate_transactions"
        elif any(not in_window(invoice, t) for t in candidates):
            classification = "outside_date_window"
        elif any(normalize(t.counterparty) != normalize(invoice.counterparty) for t in candidates):
            classification = "counterparty_conflict"
        elif (
            not direct
            and len(
                [
                    i
                    for i in invoices
                    if i.status == "OPEN"
                    and normalize(i.counterparty) == normalize(invoice.counterparty)
                    and i.currency == invoice.currency
                    and i.kind == invoice.kind
                ]
            )
            > 1
        ):
            classification = "ambiguous_counterparty"
        else:
            total = sum(abs(t.amount_cents) for t in candidates)
            if total > invoice.amount_cents:
                classification = "overpayment"
            elif total < invoice.amount_cents:
                classification = "partial_payment" if len(candidates) > 1 else "underpayment"
            elif len(candidates) > 1:
                classification = (
                    "split_payment" if direct and len(candidates) <= 6 else "ambiguous_counterparty"
                )
            else:
                classification = "reference_exact" if direct else "date_window"
    total = sum(
        abs(t.amount_cents)
        for t in candidates
        if t.currency == invoice.currency and right_direction(invoice, t)
    )
    evidence = {
        "invoice": invoice_snapshot(invoice),
        "transactions": [transaction_snapshot(t) for t in candidates],
        "transaction_ids": [t.id for t in candidates],
        "invoice_ids": [invoice.id],
        "invoice_amount_cents": invoice.amount_cents,
        "candidate_amount_cents": total,
        "difference_cents": total - invoice.amount_cents,
        "currency": invoice.currency,
        "classification": classification,
        "date_window": "issue minus 7 days through due plus 30 days",
        "explanation": f"{classification.replace('_', ' ').capitalize()}: {len(candidates)} candidate(s); eligible {invoice.currency} total {total} cents against {invoice.amount_cents} cents.",
        "verified": classification in SAFE_METHODS,
    }
    return evidence
