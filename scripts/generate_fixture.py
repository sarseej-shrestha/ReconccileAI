"""Generate the versioned, fictional fixture without random or clock-dependent values."""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
invoices = []
transactions = []
for n in range(1, 25):
    invoices.append(
        dict(
            id=f"INV-{n:03}",
            invoice_number=f"INV-{n:03}",
            counterparty=f"Fable Company {n:02}",
            amount_cents=10000 + n * 1000,
            currency="USD",
            issue_date="2026-09-01",
            due_date="2026-09-30",
            kind="payable" if n == 22 else "receivable",
        )
    )


def tx(n, amount=None, description=None, **kw):
    inv = invoices[n - 1]
    i = len(transactions) + 1
    row = dict(
        id=f"TX-{i:03}",
        external_reference=f"FICTIONAL-{i:04}",
        counterparty=inv["counterparty"],
        amount_cents=amount or inv["amount_cents"],
        currency="USD",
        date="2026-09-15",
        description=description if description is not None else inv["id"],
        source="Fictional Demo Bank",
    )
    row.update(kw)
    transactions.append(row)
    return row["id"]


expected = {}
for n in range(1, 9):
    expected[f"INV-{n:03}"] = {
        "classification": "reference_exact",
        "transaction_ids": [tx(n)],
    }
expected["INV-009"] = {
    "classification": "date_window",
    "transaction_ids": [tx(9, description="Customer payment")],
}
invoices[9]["amount_cents"] = 125000
expected["INV-010"] = {
    "classification": "split_payment",
    "transaction_ids": [tx(10, 75000), tx(10, 50000)],
}
tx(11)
tx(11)
tx(13, 150000)
tx(14, 10000)
tx(14, 5000)
tx(15, 17000)
tx(16, currency="EUR")
tx(17, description="INV-017 INV-018")
for n in (19, 20):
    invoices[n - 1]["counterparty"] = "Fable Orchard Labs"
    invoices[n - 1]["amount_cents"] = 33000
tx(19, description="Orchard payment")
tx(21, date="2025-01-10")
expected["INV-022"] = {
    "classification": "reference_exact",
    "transaction_ids": [tx(22, -32000)],
}
tx(23, -33000)
tx(24, description="INV-UNKNOWN")
for n in range(10):
    tx(
        1,
        4000 + n * 100,
        description="Unallocated fictional receipt",
        counterparty=f"Fable Unknown {n}",
    )
for n, classification in {
    11: "duplicate_transactions",
    12: "missing_payment",
    13: "overpayment",
    14: "partial_payment",
    15: "underpayment",
    16: "cross_currency",
    17: "conflicting_references",
    18: "conflicting_references",
    19: "ambiguous_counterparty",
    20: "ambiguous_counterparty",
    21: "outside_date_window",
    23: "payment_direction",
    24: "unsupported_reference",
}.items():
    expected[f"INV-{n:03}"] = {"classification": classification, "transaction_ids": []}
path = ROOT / "data/synthetic"
path.mkdir(parents=True, exist_ok=True)
(path / "records.json").write_text(
    json.dumps({"invoices": invoices, "transactions": transactions}, indent=2) + "\n"
)
(path / "labels.json").write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n")
print(f"Generated {len(invoices)} invoices and {len(transactions)} transactions")

# CSV fixtures use the same records and preserve signed integer cents.
for filename, rows in [("invoices.csv", invoices), ("transactions.csv", transactions)]:
    with (path / filename).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
