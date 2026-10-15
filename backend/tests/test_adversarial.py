import pytest
from sqlalchemy import select

from app.models import BankTransaction, Invoice
from app.services.matching import classify


@pytest.mark.parametrize(
    "change,expected",
    [
        ({"amount_cents": 10999}, "underpayment"),
        ({"amount_cents": 11001}, "overpayment"),
        ({"amount_cents": -11000}, "payment_direction"),
        ({"currency": "GBP"}, "cross_currency"),
        ({"counterparty": "Fable Company O1"}, "counterparty_conflict"),
        ({"description": "INV-001 and INV-999"}, "conflicting_references"),
    ],
)
def test_perturbed_evidence_abstains(loaded, change, expected):
    with loaded.app.state.db.session(write=True) as s:
        tx = s.get(BankTransaction, "TX-001")
        for key, value in change.items():
            setattr(tx, key, value)
        evidence = classify(
            s.get(Invoice, "INV-001"),
            list(s.scalars(select(BankTransaction))),
            list(s.scalars(select(Invoice))),
        )
        assert evidence["classification"] == expected
        assert not evidence["verified"]


@pytest.mark.parametrize("amount", [True, 0, 1.1, "11000", 1000000000001])
def test_invalid_monetary_input_fails(client, amount):
    record = {
        "id": "TX-1",
        "external_reference": "BANK-1",
        "counterparty": "Fable",
        "amount_cents": amount,
        "currency": "USD",
        "date": "2026-01-01",
        "description": "receipt",
        "source": "demo",
    }
    assert client.post("/api/import", json={"transactions": [record]}).status_code == 422
    assert client.get("/api/transactions").json() == []
