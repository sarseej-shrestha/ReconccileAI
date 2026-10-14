import csv
import io


def test_csv_roundtrip_and_validation(client):
    header = "id,invoice_number,counterparty,amount_cents,currency,issue_date,due_date\n"
    row = "INV-CSV,INV-CSV,Fictional Import,12345,USD,2026-01-01,2026-01-31\n"

    def send(content):
        return client.post(
            "/api/import/csv?kind=invoices", files={"file": ("demo.csv", content, "text/csv")}
        )

    assert send(header + row).status_code == 200
    assert send(header + row).json()["unchanged"] == 1
    assert send(header + row.replace("12345", "123.45")).status_code == 422
    assert send(header + row.replace("12345", "99999")).status_code == 409
    assert len(client.get("/api/invoices").json()) == 1
    assert (
        client.post("/api/import/csv?kind=unknown", files={"file": ("x.csv", header)}).status_code
        == 422
    )


def test_csv_transaction_and_atomic_conflict(client):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "id",
            "external_reference",
            "counterparty",
            "amount_cents",
            "currency",
            "date",
            "description",
            "source",
        ]
    )
    writer.writerow(
        ["TX-CSV", "EXT-CSV", "Fable", -100, "USD", "2026-01-01", "Vendor payment", "Demo"]
    )
    assert (
        client.post(
            "/api/import/csv?kind=transactions", files={"file": ("tx.csv", out.getvalue())}
        ).status_code
        == 200
    )
    assert client.get("/api/transactions").json()[0]["amount_cents"] == -100


def test_exception_rerun_and_currency_separated_metrics(loaded):
    loaded.post("/api/reconcile")
    before = loaded.get("/api/exceptions").json()
    assert len(before) == 24
    assert loaded.post("/api/reconcile").json()["new_exceptions"] == 0
    assert loaded.get("/api/exceptions").json() == before
    metrics = loaded.get("/api/overview").json()
    assert set(metrics["payment_volume"]) == {"USD", "EUR"}
    assert metrics["matching_rate"] == 0
    assert metrics["pending_approvals"] == 11


def test_audit_export_filters_and_no_mutation_api(loaded):
    loaded.post("/api/reconcile")
    events = loaded.get("/api/audit").json()
    assert events[0]["action"] == "reconciliation_executed"
    filtered = loaded.get("/api/audit?action=proposal_generated").json()
    assert len(filtered) == 11
    assert all(e["correlation_id"] and e["new_state"] for e in filtered)
    assert loaded.delete("/api/audit").status_code == 405
    assert loaded.put("/api/audit").status_code == 405


def test_audit_orm_is_append_only(loaded):
    import pytest
    from sqlalchemy import select

    from app.models import AuditEvent

    with pytest.raises(ValueError, match="append-only"):
        with loaded.app.state.db.session(write=True) as session:
            session.scalars(select(AuditEvent)).first().reason = "rewritten"
    with pytest.raises(ValueError, match="append-only"):
        with loaded.app.state.db.session(write=True) as session:
            session.delete(session.scalars(select(AuditEvent)).first())
