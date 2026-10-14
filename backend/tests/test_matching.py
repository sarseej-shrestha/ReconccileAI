import json
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import BankTransaction, Invoice
from app.services.matching import classify

LABELS = json.loads(
    (Path(__file__).resolve().parents[2] / "data/synthetic/labels.json").read_text()
)


@pytest.mark.parametrize("invoice_id", sorted(LABELS))
def test_labeled_classification(loaded, invoice_id):
    with loaded.app.state.db.session() as session:
        invoice = session.get(Invoice, invoice_id)
        evidence = classify(
            invoice,
            list(session.scalars(select(BankTransaction))),
            list(session.scalars(select(Invoice))),
        )
        assert evidence["classification"] == LABELS[invoice_id]["classification"]
        if evidence["verified"]:
            assert evidence["transaction_ids"] == LABELS[invoice_id]["transaction_ids"]
            assert evidence["difference_cents"] == 0


def test_split_and_rerun_are_stable(loaded):
    first = loaded.post("/api/reconcile")
    assert first.status_code == 200
    assert first.json()["new_proposals"] == 11
    assert loaded.post("/api/reconcile").json()["new_proposals"] == 0
    proposals = loaded.get("/api/proposals").json()
    split = next(p for p in proposals if p["matching_method"] == "split_payment")
    assert split["proposed_amount_cents"] == 125000
    assert split["evidence"]["candidate_amount_cents"] == 75000 + 50000
    assert split["verification"]["valid"]
