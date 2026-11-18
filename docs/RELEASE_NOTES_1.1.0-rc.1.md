# RepoLens 1.1.0-rc.1 — Phase 11 release candidate

**Not a production-certified release.** Release candidate prepared 12 November 2026.

## Maintained features

Public GitHub analysis and evidence-backed reports, persistent RAG conversations, stale SHA detection, PR/diff analysis and GitHub Action comments, team workspaces, onboarding checklists, dependency security scanning, source-confirmed code-flow visualizations, local Ollama mode and a public gallery. Existing RepoLens dashboard/landing design preserved.

## Phase 11 additions

- Single-instance Docker Compose production reference with PostgreSQL and Caddy automatic HTTPS; app and database private to the Compose network.
- Production trusted-host checking, HSTS on HTTPS, clickjacking and permissions response headers; existing CSRF and secure-session design preserved.
- Offline local-state backup/restore that checks file hashes and refuses overwrite/traversal/symlinks; PostgreSQL backup documented separately.
- Evidence-based strict release gate that does not confuse 20 unreviewed source snapshots with 20 approved full AI reports.
- Broader release ZIP privacy exclusions and safe packaged artifacts.
- CI and local release verification workflow, auth/security HTTP tests, browser outage tests and TDD regressions.

## Known release blockers

- Real Google/GitHub OAuth and Gemini/Ollama behavior require the operator's accounts/models and cannot be certified offline.
- Actual production HTTPS, PostgreSQL recovery, concurrency and deployment rollback must be rehearsed on the user's server.
- Phase 10 has 20 source snapshots but **0 manually approved full AI reports** in this starting ZIP; generation/review/publication remains mandatory.
- Security scanning is a bounded software-dependency assessment, not a guarantee of no vulnerabilities; code flow is static evidence, not complete runtime tracing.
- Multi-replica HA and Ollama container networking are not configured in the reference Compose stack.

## Version support matrix (target; not all live-certified)

| Component | Target | Evidence scope |
|---|---|---|
| macOS Apple Silicon | Python >=3.11, Node 22/24 | Previously used development target; reverify on actual Mac |
| Linux containers | Python 3.12, Node 22 (frontend build) | Dockerfile reference; deploy and test externally |
| PostgreSQL | PostgreSQL 17 + psycopg | CI service integration; production backup/restore separate |
| SQLite | Local accounts/conversations and job state | Local default and offline migration tooling |
| Gemini | Model defined in `backend/core/config.py` | Key/quota and live provider must be tested |
| Ollama | `llama3.2` + `nomic-embed-text` defaults | Requires running local models and private-path approval |
| Browsers | Chromium via Playwright | Local mocked browser tests; live OAuth separate |

See `docs/PHASE_11_OPERATIONS.md`, `docs/PHASE_11_VERIFICATION.md` and `docs/FINAL_RELEASE_VERIFICATION.md`.
