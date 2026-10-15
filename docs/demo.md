# Reproducible 90-second demonstration

## Before the interview

Install dependencies using the README. Set `LLM_API_KEY` empty to demonstrate the honest rule-generated mode. Stop any running browser harness, then run:

```bash
source .venv/bin/activate
python -m app.cli reset --yes
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
cd frontend
npm run build
npm start
```

Open http://localhost:3000. The initial fixture contains 24 invoices and 34 transactions. Reset discards local audit history by explicit operator choice; it is never exposed as a web endpoint. Do not reset a database whose history you want to retain.

## The demonstration

| Time | Action | Explain |
| --- | --- | --- |
| 0–10s | Show Overview: 24 invoices, 34 transactions, USD and EUR volumes listed separately. | “Amounts are stored in integer cents. Currency totals are never mixed.” |
| 10–22s | Click **Run reconciliation**. Observe 11 proposals and 24 exception records. | “Deterministic rules identify candidates. Nothing has been posted.” |
| 22–35s | Open **Exceptions**, then **Investigate INV-010**. | “This USD 1,250 invoice has two payments: USD 750 and USD 500.” |
| 35–49s | Click **Investigate evidence**, expand **3 read-only tool calls**. | “This run is labeled Rules. Without credentials, the same evidence workflow remains functional. An optional model can call only read tools.” |
| 49–61s | Click **Approve proposal**, enter “Verified references, currency, and 750 + 500 = 1250”, confirm. | “The human decision is recorded, and the server revalidates the evidence.” |
| 61–74s | Click **Apply to simulated ledger**. | “Two ledger entries, their idempotency result, and state changes commit atomically.” |
| 74–84s | Click **Retry same writeback**. Observe **Additional ledger entries: 0**. | “The existing operation is returned. A second key also cannot post this proposal twice.” |
| 84–90s | Open **Audit explorer**, filter `idempotent_retry` or export JSON. | “The evidence, approval, posting, and retry all have an inspectable audit trail.” |

For a longer demonstration, reject `INV-002` and show that it has no apply control; the API also returns 409 if posting is attempted. Investigate `INV-016` to show currency conflict abstention. Re-run reconciliation after posting to show that applied ledger records remain unchanged.

## API replay demonstration

The UI retains the original posting version and key in session storage. The same behavior can be exercised directly using a real proposal ID and its approved version:

```bash
curl -s http://127.0.0.1:8000/api/proposals
# Replace PROPOSAL_ID with a reviewed, APPROVED proposal ID; version is normally 2.
curl -s -X POST http://127.0.0.1:8000/api/proposals/PROPOSAL_ID/apply \
  -H 'Content-Type: application/json' \
  -H 'X-Reviewer-Token: local-demo-reviewer' \
  -H 'Idempotency-Key: interview-split-operation' \
  -d '{"version":2}'
```

Repeat that exact request. For the split case, the first response has `replayed: false` and `additional_entries: 2`; the second has `replayed: true` and `additional_entries: 0`, with the same operation and entry IDs. Reuse the key with a different version to demonstrate a 409 conflict.

## Questions to prepare

**Why isn't schema validation enough to make model output safe?** A schema can describe a nonexistent invoice perfectly. Entity lookups, exact cents/currency checks, evidence fingerprints, and independent allocation verification establish financial validity. The model never receives write functions.

**How do you prevent duplicate effects after a timeout?** Store the request fingerprint and result in the same database transaction as the ledger. Retrying an identical key returns the result; unique proposal operations and transaction consumption prevent duplication even with a different key.

**What changes under PostgreSQL and external bank integration?** Replace SQLite's database-wide writer reservation with transaction-scoped row locking and robust unique-key race handling. Add migrations and an outbox. External adapters need their own idempotency and recovery because a database transaction cannot atomically commit a remote bank call.
