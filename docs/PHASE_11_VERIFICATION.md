# Phase 11 — Final integrated verification and evidence checklist

**Version:** 1.1.0-rc.1  
**Release decision:** NOT FULLY VERIFIED (release candidate; do not label production-ready)  
**Date:** 2026-11-12

This document implements the Phase 11 acceptance definition from `RepoLens_Complete_12_Phase_Upgrade_Roadmap_2026-11-11.md`. The project has a local release workflow, HTTPS deployment reference, state backup/restore and strict evidence matrix. **Installation, mocked test execution and checked-in example gallery pages do not prove actual public deployment or real AI report publication.**

## Four testing approaches

| Approach | Exact command | What it covers | Scope/limitation |
|---|---|---|---|
| 1. Unit | `python -m pytest -q` and `cd frontend && npm test` | Backend functions and frontend state/UI logic | Needs Python/Node dependencies; provider calls often mocked |
| 2. Integration | `python scripts/verify_release_http.py` | Started FastAPI server, synthetic sessions, CSRF/auth boundaries, persistence after restart | Uses synthetic accounts; does not exercise Google/GitHub OAuth consent |
| 3. Browser E2E | `cd frontend && npm run test:browser` | Chromium navigation, onboarding, gallery, route tracing, outages, component workflows | Browser suite stubs some APIs; separate live end-to-end walkthrough remains mandatory |
| 4. Test-driven regressions | `python -m pytest -q tests/test_phase11_release_tdd.py tests/test_phase11_runner_tdd.py tests/test_phase11_http.py` | Backup tampering/traversal, source packaging, release gate, production HTTP headers, runner evidence | `test_phase11_http.py` skips without `authlib`; no live deployment implied |

`node --test tests-js/*.test.mjs` verifies the GitHub Action comment renderer and related Node logic. `cd frontend && npm run build` verifies Vite production compilation. These two additional checks are included in the full local runner.

### Automated local run

In the project root with `.venv` activated and `frontend/node_modules` installed:

```bash
bash scripts/verify_phase11.sh
```

This invokes `scripts/phase11_verify.py` to execute preflight + Python suite + frontend tests + build + Playwright + HTTP integration + GitHub Action unit tests. The runner executes the next check even when an earlier one fails and writes **private** logs, a JSON summary and a release-gate assessment to a timestamped folder inside `reports/`. Python-suite skips automatically block the `python_suite` gate until resolved or explicitly assessed separately. It only automatically passes gates that genuinely correspond to those exact local commands; it does **not** auto-pass real OAuth, hosted HTTPS or the 20 reviewed gallery requirement. The shell returns nonzero when any local check fails or is blocked.

Use `python scripts/phase11_verify.py --only python_suite frontend_unit --output-dir reports/my-new-run` for a smaller rerun. Every output directory must be empty/new; the tool intentionally never overwrites earlier evidence. **Do not commit or upload logs:** they may contain private paths, account data or source snippets.

### Separate live acceptance (manual, dated, redacted evidence)

1. **Real OAuth/security:** sign in/out with Google **and** GitHub, validate secure session cookies, CSRF, Origin and Host protections, cross-user access denial and revoked workspace memberships. Check invalid/expired tokens and invitations.
2. **Real RAG:** index a fresh pinned Python repository, ask cited follow-ups, restart and reload history, change branch SHA and reindex, evaluate actual citations and quotas.
3. **PR and GitHub Action:** on a controlled PR, compare commits, open a PR and verify one bot comment, update the PR and verify the same comment is edited; test fork events and denied permissions.
4. **Onboarding/security/code flow:** follow a real checklist and PDF/share-revocation workflow, inspect version-matched security advisories, and verify source-confirmed call chains across Python, JS/TS and Go.
5. **Ollama:** generate local embeddings and local answers using approved local repositories and verify no data was sent to Gemini/cloud.
6. **Public gallery:** generate, manually review and publish **20 full AI architecture reports**. Confirm checksum-bound publication receipts and links on the actual public origin, not just local source snapshots.
7. **Persistence/operations:** rehearse cold Chroma/cache/auth backup+restore, PostgreSQL `pg_dump`/restore to a **separate database**, migrations, freshness worker restart, interrupted jobs, concurrent access and rate-limit recovery.
8. **Production/mobile:** use real HTTPS with correct DNS and OAuth callbacks, check HSTS/Host/headers, view on phone/tablet and keyboard-only, errors and empty states; confirm rollback with intact data.
9. **Cross-feature journey:** repeat the complete ten-feature journey with two distinct real accounts and at least three pinned public repos (Python, JS/TS, Go).

Record the evidence in a **private** copy of `docs/PHASE11_EVIDENCE_TEMPLATE.json` (all 19 gates). For each checked gate use a JSON object: `{"status":"PASS","evidence":"Date, environment, exact test and anonymized result/log location"}`. Use `FAIL` for reproducible defects, `BLOCKED` for unperformed or inaccessible external checks.

```bash
python scripts/phase11_gate.py --evidence reports/phase11-evidence.json --output reports/phase11-release.json --strict
```

Exit code `2` means **NOT FULLY VERIFIED**. `PASS` evidence in this file is an *operator attestation*; only local checksum-bound gallery receipts are programmatically checked. A complete gate also requires human accuracy review and live deployment evidence.

## Release hygiene and recovery

- `python scripts/package_release.py "$HOME/Downloads/RepoLens_Phase11_RC.zip"` builds a source-only ZIP without private `.env`, databases, virtual environments or caches.
- `python scripts/phase11_state.py --backup "$HOME/repolens-private-backup.zip"`, `--verify` and `--restore ... --destination "$HOME/repolens-restore-test"` implement **cold local state** backup and test restore. Stop the server and workers first. Encrypt backups; SHA-256 alone is not authenticity or encryption.
- PostgreSQL is **not** included in local ZIP state backups. See `docs/PHASE_11_OPERATIONS.md` for separate dump/restore procedures.
- `deployment/compose.production.yml` provides a **single-instance reference**, not a deployed or audited production environment. Keep keys outside source control and rehearse rollback before public launch.
- For known gaps, risk boundaries and platform matrix, read `docs/RELEASE_NOTES_1.1.0-rc.1.md`.
