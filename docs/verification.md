# Verification report

## Local execution

- **74 backend tests passed**, with zero failures. One upstream Starlette/AnyIO deprecation warning is present in the local environment.
- Ruff lint and formatting checks passed for the backend, evaluation runner, and fixture generator.
- Frontend ESLint, generated route types, strict TypeScript checking, and the Next.js production build passed.
- The real browser workflow passed 11 checks: import, 11 deterministic proposals, investigation, approval, split settlement, zero-effect replay, rejection enforcement, CSV upload, audit export/filter, mobile layout, and absence of uncaught browser errors.
- The browser test started both actual servers and initialized a new temporary SQLite database. It observed two ledger entries totaling 125,000 cents and zero additional entries after retry.
- The evaluation runner completed with 11 true-positive candidate matches, no false positives/negatives, 14/14 correct invoice exception labels, and 13/24 abstentions. See `evaluation/results.json` for the actual run output and `docs/evaluation.md` for limitations.
- Desktop and mobile screenshots were visually inspected. The chart renders actual proposal counts, the approval dialog captures a reason, and ledger/audit controls use real endpoints.

## Clean-install CI

[GitHub Actions run 38688170027](https://github.com/sarseej-shrestha/ReconccileAI/actions/runs/38688170027) passed all three jobs on Ubuntu: backend installation/lint/tests/evaluation, frontend installation/lint/type checking/production build, and real-browser end-to-end verification. The run tested integrated commit `7e1ec99aa55da65adc8723cd28172dec361da898`. Final correctness follow-ups add complete import snapshots and tests for exact JSON serialization beyond JavaScript’s safe integer range.

## Environment and reproducibility

Local verification used Python 3.13.5 and Node 23.10.0 on macOS. The project requests Node 24 LTS, and CI is configured for Node 24 and Python 3.13. The local Node version produces an engine warning, but lint, type checking, build, and real browser tests completed.

Package-registry access was unavailable in the execution sandbox. Python tests used cached wheels plus official tagged source checkouts for FastAPI 0.135.2, Starlette 0.52.1, Uvicorn 0.42.0, pydantic-settings 2.13.1, python-multipart 0.0.22, and python-dotenv 1.2.2. Frontend installation completed from the local npm cache. No dependency source was vendored into the repository. Standard clean-install commands are in the README; CI performs those installs on Ubuntu.

No live LLM request was made. The optional adapter's protocol, schema, tool behavior, failures, and fallback were tested with controlled provider responses; the demonstration used the clearly labeled deterministic investigator.

## Repository publication

All implementation milestones use Sarseej Shrestha and the verified `sarseej.shrestha@selu.edu` address for author and committer. The workspace's Git metadata was read-only, and direct Git push transport could not resolve GitHub inside the sandbox. The project was committed in an isolated checkout and published through authenticated GitHub Git Data API calls, with non-forced branch advances and remote verification. This is API publication, not a claim that `git push` succeeded.

The source repository remains `sarseej-shrestha/ReconccileAI`. No alternative GitHub repository was created. No existing contributor history was rewritten. The feature branches retain their milestone snapshots, and tested work is integrated linearly into `main`.

## Limits of the checks

The test suite establishes behavior for this prototype and its labeled/adversarial cases, not production certification, financial compliance, or a statistical safety guarantee. Concurrency tests use a local file-backed SQLite database; they do not simulate distributed bank execution. There is no real authentication, bank connection, deployment, or production-grade ledger. See `docs/design-decisions.md` before extending it to real financial data.
