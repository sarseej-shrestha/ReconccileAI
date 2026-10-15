# Design decisions

## Determinism owns financial authority

Language models are useful for deciding what evidence to inspect, but cannot establish that money moved or that a reference exists. A strict schema prevents malformed output; independent reference and amount checks prevent well-formed hallucinations. The final explanation renders verified facts, while the model adapter supplies an optional bounded investigation path. Requiring a human approval after verification keeps the operational boundary visible and testable.

No fuzzy match can authorize posting. Exact normalized counterparties plus amount and date may produce a candidate, but still require approval. Overpayments, partial payments, and currency conflicts abstain. This sacrifices automation coverage to avoid silently consuming unrelated funds.

## One relational transaction rather than a queue

SQLite plus SQLAlchemy keeps the local demonstration reproducible. Acquiring the write reservation before reads makes approval and posting races easy to reason about. Unique proposal-operation and transaction-consumption constraints enforce invariants even if an application check regresses. Idempotency responses are stored in the same transaction as ledger effects; a separate cache would introduce a failure window.

The cost is serialized writers and modest capacity. The database timeout becomes a retryable 503. No Redis, distributed queue, or microservice is necessary for this scale. The application has clear service boundaries for later replacement.

## Evidence snapshots plus fresh reads

Snapshots explain historical decisions. Fresh classification and fingerprints catch stale evidence and new conflicts at approval and application time. Keeping both avoids accepting an old proposal merely because its monetary total remains unchanged. Import replay cannot silently edit established financial evidence.

## Explicit prototype accounting

The ledger is a settlement journal, not a complete balanced general ledger. It records real application-generated receipt/payment effects linked to an operation, human decision, invoice, and bank transaction. Opening demo records are not fabricated as already posted entries. The 90-second demo creates the relevant ledger records through the actual controls.

One invoice per settlement and whole-transaction consumption keep the allocation problem bounded. Partial-payment classification does not imply incremental posting support. No currency conversion, refund allocation, fee write-off, or cross-invoice netting is attempted.

## Interface choices

Next.js, strict TypeScript, Tailwind, an adapted shadcn/ui button pattern, and Recharts provide a compact operations workspace. Native modal dialogs provide keyboard focus containment. Plain fetch with explicit refresh after mutations is sufficient for this small single-user interface; no optimistic financial updates hide failed backend decisions. Charts disable animation so the state is visible immediately. Financial labels use integer-aware formatting.

The backend is required for every substantive action. A zero-state chart and empty ledger are real empty states, never sample success responses. Authentication is explicitly simulated and the token is a demonstrative role gate, not a secret security boundary.

## Production readiness

Before handling real financial records:

- Replace the reviewer token with OIDC authentication, server-side roles, least-privilege authorization, tenant isolation, session/CSRF controls, and approval separation of duties.
- Move to PostgreSQL with Alembic migrations, transaction retry policy, explicit locking, invariant-preserving indexes, backups, and tested disaster recovery. `create_all` does not upgrade an existing schema.
- Implement balanced journal entries, reconciliation reversals, account mappings, currency-specific minor units, fee handling, partial allocations, and finance-approved exception policies.
- Add a transactional outbox and independently idempotent external adapters before any bank or accounting-system writeback. Database commit does not imply an external service committed.
- Add structured operational logs, traces, metrics, alerting, rate limits, upload/content limits at the proxy, durable failure reporting, cancellation, and load tests.
- Secure credentials in a managed secret store; enforce provider egress, data minimization, retention, encryption, privacy controls, and prompt/output logging policy.
- Expand adversarial and held-out evaluation across real-world counterparty variation, duplicated imports, many-to-many payments, date boundaries, and distribution drift. Have finance specialists review false positives and proposed allocations.
- Add audit retention, export pagination, tamper-evident external retention if required, and administrative access logging. Application append-only enforcement does not make the database immutable.

## References

The transaction design follows [SQLite's transaction semantics](https://www.sqlite.org/lang_transaction.html) and [SQLAlchemy's SQLite transaction guidance](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html). Frontend checking runs ESLint separately from the production build, following [Next.js installation guidance](https://nextjs.org/docs/app/getting-started/installation).
