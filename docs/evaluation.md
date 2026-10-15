# Evaluation methodology

Run `python -m evaluation.run` from the root after installing the backend. It creates a temporary SQLite database, loads `data/synthetic/records.json`, runs the real reconciliation service, independently verifies every generated proposal, and compares invoice/transaction sets with `data/synthetic/labels.json`. The generated report is `evaluation/results.json`. Evaluation never modifies the demo database.

## Measured baseline

| Metric | Result |
| --- | ---: |
| Invoices / bank transactions | 24 / 34 |
| Expected full-settlement candidate matches | 11 |
| Correct candidate matches | 11 |
| False positives | 0 |
| False negatives | 0 |
| Matching precision | 100% |
| Matching recall | 100% |
| Invoice exception classification accuracy | 100% (14/14) |
| Abstentions | 13/24 (54.17%) |

A match is correct only when both the invoice and the complete transaction-ID set equal the label. A wrong subset is a false positive and leaves an expected match missing. Precision is TP/(TP+FP); recall is TP/(TP+FN). Expected safe cases include exact reference matches, one unique date-window match, the split payment, and a vendor payment with the correct negative sign.

Exception accuracy covers the 14 invoice labels outside `reference_exact` and `date_window`, including the correctly identified split-payment review case. The ten unmatched transactions produce separate exception records and are checked by integration tests; they are not included in this invoice classification denominator. Abstention counts invoices for which no safe proposal is generated. Requiring human review for the split case is not counted as matching abstention.

These labels were designed alongside the deterministic rules. They are a regression fixture, not an independent statistical benchmark. The results measure deterministic candidate generation, not automatic posting success, financial business accuracy, or LLM reasoning quality. Model confidence is never interpreted as probability. No paid live-provider evaluation was performed.

## Reliability tests

A separate precision test aggregates 9,008 transactions with individually valid cent amounts and verifies that totals beyond JavaScript’s safe integer range survive JSON parsing exactly. This is a correctness test, not a throughput benchmark.

The backend suite exercises fixture labels, one-cent perturbations, sign and currency changes, conflicting references, duplicate detection, strict monetary inputs, atomic CSV imports, and repeat reconciliation. Approval tests cover authorization, rejection, stale versions, changed evidence, newly imported conflicts, forged allocations, and repeated decisions.

Concurrency tests run six simultaneous posting requests against a file-backed SQLite database using both identical and distinct keys; only one two-entry split settlement takes effect. Four concurrent approvals produce one successful decision. Failure injection after ledger flush but before idempotency persistence proves that operation, ledger, invoice, and proposal changes roll back together. Another test tries to consume a transaction through a separate proposal.

Investigator tests cover structured output, invalid fields, false financial claims, nonexistent references, tool failures, empty evidence, tool budgets, timeouts, malformed responses, prompt injection text, and attempted writeback tools. Adapter tests exercise the actual compatible-provider JSON/tool-call loop with a controlled HTTP response; they do not pretend to be real model inference.

The browser harness uses the actual production Next.js build and actual FastAPI server with a temporary database. It imports data, reconciles, investigates the split, approves, posts, retries, checks ledger totals, rejects a second proposal, confirms posting rejection, uploads CSV, downloads audit JSON, and checks mobile layout and uncaught browser errors.

## Next evaluation work

A production evaluation would need an independently labeled holdout set, finance-reviewed allocation decisions, many-to-many payment cases, misspelled counterparties, currencies with other minor units, large import volumes, date boundary sampling, and operational fault tests around external accounting adapters. A low false-positive rate on this small fixture cannot establish safety on unseen financial data.
