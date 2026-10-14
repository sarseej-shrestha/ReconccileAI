def test_health_and_idempotent_import(loaded):
    assert loaded.get("/api/health").json()["status"] == "ok"
    assert len(loaded.get("/api/invoices").json()) == 24
    assert len(loaded.get("/api/transactions").json()) == 34
    assert loaded.post("/api/demo/load").json() == {
        "invoices": 0,
        "transactions": 0,
        "unchanged": 58,
    }


def test_integer_money_and_atomic_import(client):
    base = dict(
        id="INV-1",
        invoice_number="INV-1",
        counterparty="Fictional",
        amount_cents=100,
        currency="USD",
        issue_date="2026-01-01",
        due_date="2026-01-31",
    )
    assert (
        client.post("/api/import", json={"invoices": [{**base, "amount_cents": 1.5}]}).status_code
        == 422
    )
    assert (
        client.post("/api/import", json={"invoices": [base, {**base, "id": "INV-2"}]}).status_code
        == 409
    )
    assert client.get("/api/invoices").json() == []
