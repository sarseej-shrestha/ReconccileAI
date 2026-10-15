# Interview notes

## Three decisions worth explaining

1. **Verification at both approval and posting.** Evidence snapshots make decisions explainable, while recomputing their fingerprint detects changed financial inputs and new conflicting transactions. The AI's output cannot bypass either check.
2. **Idempotency belongs in the transaction.** The ledger, state transitions, audit success events, and stored response commit together. Database uniqueness blocks duplicate transaction consumption and duplicate proposal operations, even with different request keys.
3. **Abstention is visible product behavior.** The UI distinguishes identified candidates, approved proposals, applied settlements, and unresolved exceptions. Cross-currency, ambiguous, and inconsistent evidence stays outside the ledger instead of being hidden behind a confidence score.

## Questions and answers

**What happens if the client times out after posting commits?** Retrying the same idempotency key and original payload returns the stored operation. If a different key targets the same proposal, its unique posting operation is returned with zero additional financial effects.

**How can imported prompt injection affect the system?** Descriptions are untrusted JSON evidence. They may cause an investigator to fail or a reference rule to abstain, but cannot register a tool or call a write service. Model references and financial claims must agree with actual database evidence; approval and posting are separate guarded endpoints.

**Why use SQLite, and how would you scale it?** It gives a reproducible, single-process deployment with transactional constraints. `BEGIN IMMEDIATE` serializes writers before they inspect shared state. PostgreSQL would use row locks, unique constraints, transactional retries, migrations, and an outbox for independently idempotent external adapters.

## Truthful resume bullets

- Built ReconcileAI with FastAPI, SQLAlchemy, and Next.js, implementing 13 reconciliation scenarios and a guarded read-only investigator; achieved 11/11 expected matches with zero false positives on a labeled 24-invoice, 34-transaction synthetic fixture.
- Engineered transactional approval and idempotent ledger workflows validated by 74 backend tests and an 11-check browser demo; six concurrent posting requests produced one settlement, and repeat writebacks created zero additional ledger entries.

The dataset figures describe a development fixture, not real customer traffic, production savings, or independently validated model performance.
