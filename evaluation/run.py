"""Evaluate deterministic candidates against versioned, hand-labeled fictional records."""

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app.db import Database
from app.models import BankTransaction, Invoice, Proposal
from app.schemas import ImportData
from app.services.importing import import_data
from app.services.matching import SAFE_METHODS, classify
from app.services.reconciliation import reconcile, verify
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]


def evaluate():
    labels = json.loads((ROOT / "data/synthetic/labels.json").read_text())
    with tempfile.TemporaryDirectory() as tmp:
        db = Database(f"sqlite:///{tmp}/evaluation.db")
        db.initialize()
        with db.session(write=True) as session:
            import_data(
                session,
                ImportData.model_validate_json((ROOT / "data/synthetic/records.json").read_text()),
                "evaluation",
            )
            reconcile(session, "evaluation")
        with db.session() as session:
            invoices = list(session.scalars(select(Invoice)))
            transactions = list(session.scalars(select(BankTransaction)))
            actual = set()
            for p in session.scalars(select(Proposal)):
                verify(session, p)
                actual.add(
                    (
                        p.allocations[0].invoice_id,
                        tuple(sorted(a.transaction_id for a in p.allocations)),
                    )
                )
            expected = {
                (key, tuple(sorted(value["transaction_ids"])))
                for key, value in labels.items()
                if value["classification"] in SAFE_METHODS
            }
            outcomes = {
                i.id: classify(i, transactions, invoices)["classification"] for i in invoices
            }
            tp, fp, fn = (
                len(actual & expected),
                len(actual - expected),
                len(expected - actual),
            )
            exception_labels = {
                key: value
                for key, value in labels.items()
                if value["classification"] not in {"reference_exact", "date_window"}
            }
            correct = sum(
                outcomes[key] == value["classification"] for key, value in exception_labels.items()
            )
            report = {
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "dataset": "synthetic-v1 (development fixture, not held-out production data)",
                "invoice_count": len(invoices),
                "transaction_count": len(transactions),
                "true_positives": tp,
                "false_positives": fp,
                "false_negatives": fn,
                "matching_precision": tp / (tp + fp) if tp + fp else 0,
                "matching_recall": tp / (tp + fn) if tp + fn else 0,
                "exception_classification_accuracy": correct / len(exception_labels),
                "exception_cases_evaluated": len(exception_labels),
                "abstention_count": sum(c not in SAFE_METHODS for c in outcomes.values()),
                "abstention_frequency": sum(c not in SAFE_METHODS for c in outcomes.values())
                / len(invoices),
                "false_positive_cases": sorted(actual - expected),
                "false_negative_cases": sorted(expected - actual),
                "classifications": outcomes,
            }
        db.engine.dispose()
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/results.json")
    args = parser.parse_args()
    result = evaluate()
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "classifications"}, indent=2))
    if (
        result["false_positives"]
        or result["false_negatives"]
        or result["exception_classification_accuracy"] != 1
    ):
        raise SystemExit(1)
