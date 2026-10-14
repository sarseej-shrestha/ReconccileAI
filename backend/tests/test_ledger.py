from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select

from app.models import BankTransaction, Invoice, LedgerEntry, Proposal

HEADERS = {"X-Reviewer-Token": "local-demo-reviewer"}


def candidate(client, invoice="INV-010"):
    client.post("/api/reconcile")
    return next(p for p in client.get("/api/proposals").json() if invoice in p["invoice_ids"])


def approve(client, p):
    return client.post(
        f"/api/proposals/{p['id']}/review",
        headers=HEADERS,
        json={"decision": "APPROVED", "version": p["version"], "reason": "Evidence checked"},
    )


def post(client, p, key="operation-test-key", version=2):
    return client.post(
        f"/api/proposals/{p['id']}/apply",
        headers={**HEADERS, "Idempotency-Key": key},
        json={"version": version},
    )


def test_sequential_replay_and_distinct_keys(loaded):
    p = candidate(loaded)
    assert approve(loaded, p).status_code == 200
    first = post(loaded, p).json()
    second = post(loaded, p).json()
    third = post(loaded, p, "different-operation-key").json()
    assert first["additional_entries"] == 2
    assert not first["replayed"]
    for result in (second, third):
        assert result["operation_id"] == first["operation_id"]
        assert result["additional_entries"] == 0
        assert result["replayed"]
    assert len(loaded.get("/api/ledger").json()) == 2
    assert post(loaded, p, version=99).status_code == 409
    ledger = loaded.get("/api/ledger").json()
    loaded.post("/api/reconcile")
    assert loaded.get("/api/ledger").json() == ledger


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_posting_has_one_effect(loaded, same_key):
    p = candidate(loaded)
    approve(loaded, p)
    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(
            pool.map(lambda n: post(loaded, p, f"parallel-key-{0 if same_key else n}"), range(6))
        )
    assert all(r.status_code == 200 for r in responses)
    assert sum(r.json()["additional_entries"] for r in responses) == 2
    assert len(loaded.get("/api/ledger").json()) == 2


def test_concurrent_approval_and_state_machine(loaded):
    p = candidate(loaded)
    assert post(loaded, p).status_code == 409
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: approve(loaded, p), range(4)))
    assert sorted(r.status_code for r in responses) == [200, 409, 409, 409]


def test_rejection_and_authorization(loaded):
    p = candidate(loaded)
    path = f"/api/proposals/{p['id']}/review"
    body = {"decision": "REJECTED", "version": 1, "reason": "Manual follow-up"}
    assert loaded.post(path, json=body).status_code == 403
    assert loaded.post(path, json=body, headers=HEADERS).status_code == 200
    assert post(loaded, p).status_code == 409
    assert approve(loaded, p).status_code == 409
    assert loaded.get("/api/ledger").json() == []
    assert loaded.get("/api/audit", params={"action": "ledger_writeback_failed"}).json()


@pytest.mark.parametrize("stage", ["approval", "posting"])
def test_stale_evidence_is_rejected(loaded, stage):
    p = candidate(loaded)
    if stage == "posting":
        approve(loaded, p)
    with loaded.app.state.db.session(write=True) as session:
        session.get(BankTransaction, p["transaction_ids"][0]).amount_cents += 1
    response = approve(loaded, p) if stage == "approval" else post(loaded, p)
    assert response.status_code == 409
    assert loaded.get("/api/ledger").json() == []


def test_new_conflicting_evidence_invalidates_proposal(loaded):
    p = candidate(loaded, "INV-001")
    with loaded.app.state.db.session(write=True) as s:
        original = s.get(BankTransaction, p["transaction_ids"][0])
        s.add(
            BankTransaction(
                id="TX-NEW",
                external_reference="new-reference",
                counterparty=original.counterparty,
                amount_cents=original.amount_cents,
                currency=original.currency,
                date=original.date,
                description=original.description,
                source="New import",
            )
        )
    assert approve(loaded, p).status_code == 409


def test_forged_allocation_rejected(loaded):
    p = candidate(loaded)
    with loaded.app.state.db.session(write=True) as s:
        s.get(Proposal, p["id"]).allocations[0].amount_cents += 100
    assert approve(loaded, p).status_code == 409


def test_failure_rolls_back_all_financial_effects(loaded, monkeypatch):
    p = candidate(loaded)
    approve(loaded, p)
    from app.services import ledger

    real = ledger.posting_result

    def fail(*args):
        raise RuntimeError("Injected after ledger flush, before result persistence")

    monkeypatch.setattr(ledger, "posting_result", fail)
    with pytest.raises(RuntimeError, match="Injected"):
        post(loaded, p)
    with loaded.app.state.db.session() as session:
        assert list(session.scalars(select(LedgerEntry))) == []
        assert session.get(Proposal, p["id"]).status == "APPROVED"
        assert session.get(Invoice, "INV-010").status == "OPEN"
    monkeypatch.setattr(ledger, "posting_result", real)
    assert post(loaded, p).json()["additional_entries"] == 2
