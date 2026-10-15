import json
from datetime import date

from sqlalchemy import insert

from app.models import BankTransaction
from app.serialization import ExactJSONResponse


def test_large_currency_aggregate_survives_javascript_json_precision(client):
    # Individually valid import amounts can sum beyond JavaScript's exact integer range.
    rows = [
        dict(
            id=f"TX-LARGE-{n}",
            external_reference=f"LARGE-{n}",
            counterparty="Fable Volume",
            amount_cents=1_000_000_000_000,
            currency="USD",
            date=date(2026, 9, 15),
            description="Fictional high-volume precision fixture",
            source="Demo",
        )
        for n in range(9008)
    ]
    rows[-1]["amount_cents"] -= 1
    with client.app.state.db.session(write=True) as session:
        session.execute(insert(BankTransaction), rows)
    response = client.get("/api/overview")
    # Simulate a JSON consumer whose numeric values use binary64, as in JavaScript.
    payload = json.loads(response.text, parse_int=float)
    assert payload["payment_volume"]["USD"] == "9007999999999999"
    assert int(payload["payment_volume"]["USD"]) == sum(row["amount_cents"] for row in rows)


def test_nested_audit_amounts_preserve_sign_and_small_integer_types():
    response = ExactJSONResponse(
        {"new_state": {"amount_cents": -(2**53 + 1)}, "small_cents": 125000, "approved": True}
    )
    payload = json.loads(response.body)
    assert payload["new_state"]["amount_cents"] == "-9007199254740993"
    assert payload["small_cents"] == 125000
    assert payload["approved"] is True
