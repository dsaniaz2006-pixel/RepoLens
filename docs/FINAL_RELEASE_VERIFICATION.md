# RepoLens Phase 11 — Final release verification report

**Version:** `1.1.0-rc.1`  
**Created:** 2026-11-12  
**Release status:** **NOT FULLY VERIFIED** — release candidate only.

## Implemented in Phase 11

- Production reference: single-instance Compose with Postgres 17 and Caddy ACME HTTPS, no publicly published database/API ports, non-root app container and persistent data volumes.
- Security hardening: production trusted-host allowlisting; HSTS only over configured HTTPS, anti-framing, content-type and permissions headers. Existing CSRF/session enforcement retained.
- Recovery: offline local-state archive with SHA-256 verification, no overwrite, symlink/traversal rejection and safe separate-directory restore; separate PostgreSQL backup/restore documentation.
- Release discipline: source ZIP excludes environment files, account databases, local indexes/caches, logs and generated reports; public gallery assets retained. Version and release notes documented.
- Regression coverage: Python Phase 11 backup/publishing TDD tests, production auth HTTP tests, evidence-runner tests, real HTTP smoke script, Node frontend/Action suites and Playwright Phase 11 browser scenarios.
- Strict 19-gate release decision: missing external evidence stays `BLOCKED`, including actual approval of 20 AI reports and public HTTPS deployment.

## Observed results in this build environment

The checked-in release candidate is **not** a representation that every suite passed. Results from this tool environment must not be conflated with the user's Mac.

| Check | Observed | Qualification |
|---|---|---|
| Python Phase 11 backup/gate TDD | **12 passed**, 1 HTTP integration test skipped | HTTP test needs missing `authlib`; full Python suite cannot collect without it |
| Frontend Node tests | **28/28 passed** | UI logic, static content, mocking scaffolds; not browser |
| GitHub Action Node tests | **3/3 passed** | Comment formatting/update isolation; not real GitHub PR |
| Python full suite | **BLOCKED** | `authlib` missing in this environment; other project dependencies also unavailable |
| Combined targeted regression suites | **31 passed, 1 failed, 1 skipped** | The failure is an import error for missing `authlib` in `test_migration_releases_runtime_leases`, not a reproduced application assertion failure |
| Vite production build | **BLOCKED** | `frontend/node_modules` not installed (`vite: not found`) |
| Playwright Chromium | **BLOCKED** | Vite/Node browser-test dependencies not installed; a separate static Chromium check was blocked from accessing localhost by this environment |
| Real OAuth, Gemini, Ollama, PostgreSQL rehearsal, public HTTPS | **BLOCKED** | Require actual services and/or credentials and explicit evidence |
| 20 complete reviewed AI gallery reports | **BLOCKED** | Source snapshot cards do not count as approved full reports |

The new evidence runner can generate a current local test report on the actual Mac:

```bash
bash scripts/verify_phase11.sh
```

Run and inspect `reports/phase11-local-*/release-gate.json` or explicitly submit dated manual attestations to `python scripts/phase11_gate.py --evidence ... --strict`. The gate has **19** entries and is only fully passing when all 19 have valid PASS evidence and the local reviewed-gallery receipts satisfy the publication requirement. A manually entered text string does **not** independently prove a hosted service passed.

## Outstanding release blockers

1. Install dependencies and run all four testing approaches, as well as Vite compilation, on the actual Mac and CI; fix all real failures.
2. Demonstrate real Google/GitHub sign-in, actual user isolation/CSRF, GitHub Action behavior, RAG with Gemini and Ollama, and source verification on Python, JS/TS, Go repositories.
3. Generate, review, approve and publish 20 complete AI gallery reports; check anonymous visibility on the actual public host.
4. Deploy HTTPS reference with proper server/domain/OAuth configuration and rehearse real PostgreSQL+local-state backup and rollback.
5. Record accessibility/mobile evaluation, rate-limit failures, worker restart/recovery, and the integrated cross-feature journey.

**Release decision:** This artifact is an installable development/release candidate. It is not a security certification or an independently verified production deployment. Stable launch requires all blockers to be resolved with evidence.

Detailed commands: `docs/PHASE_11_OPERATIONS.md` and `docs/PHASE_11_VERIFICATION.md`.
