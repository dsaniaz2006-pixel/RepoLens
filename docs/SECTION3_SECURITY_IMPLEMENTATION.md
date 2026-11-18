# RepoLens Section 3 — Website security (2026-11-13)

This is an **additive** hardening update to the Section 2 project. It does not alter the Gemini/ChromaDB index format, existing Google/GitHub identities, or frontend navigation. The user should back up Neon before applying `auth_0003`.

## What changed

1. `backend/security/controls.py`: strict GitHub URL validation, bounded question validation without brittle prompt phrase blocklists, redacted public validation errors, fail-closed production settings, and an allowlist for audit actions. No arbitrary request URL/body is recorded.
2. `backend/database/schema_definitions.py` and `backend/database/migrations_auth/versions/auth_0003_security_audit.py`: adds `audit_events` with indexed user/time lookup. It does not rewrite users, sessions, or API keys. Downgrades refuse to drop non-empty audit history.
3. `backend/auth/auth.py`: records API key creation/revocation, successful and failed OAuth logins, logout, revoke-all sessions, and successful allowlisted workspace/conversation/report mutations. `/api/auth/audit` lists the signed-in user's own last 20 records, with no tokens or raw provider errors. Strengthens CSP, browser isolation headers and production env checks.
4. `backend/api/api.py` and `backend/api/product_api.py`: validates repository URLs before expensive operations, rejects control bytes in chat questions and workspace names, and returns bounded 422 errors without echoing Pydantic's input field or request secrets. Provider error categories and user-facing text are retained with secret redaction.
5. `frontend/public/join.html` and `frontend/public/join.js`: removes the inline JS so `script-src 'self'` permits a working invite flow; the invitation is not sent to third-party analytics or stored in JS.
6. `frontend/src/features/settings/SecuritySettings.jsx`: adds Recent security activity under existing dark/light Settings. `/api/auth/audit` failures do not disable existing key/device controls.
7. `backend/ai/analyzer.py` and `backend/ai/qa.py`: explicit repository/history data-versus-instruction boundaries. Existing source evidence and citation validation remain in place.

## Preserved interfaces

- `GET /api/auth/me`, `GET|POST /api/auth/keys`, `DELETE /api/auth/keys/{id}`, `GET /api/auth/sessions`, `DELETE /api/auth/sessions/all` remain unchanged.
- New `GET /api/auth/audit` requires a browser cookie (not a bearer API key); it returns `{ "events": [...] }` with `{id, action, target, created_at}` and no credentials.
- Existing chat, workspace, CLI, RAG and report routes are not renamed.
- `REPOLENS_ENV=development` remains appropriate for local macOS. Production now rejects absent PostgreSQL URLs, weak/missing session secret, non-HTTPS origins, and missing OAuth providers.

## Mandatory safe Neon upgrade

1. Stop the old RepoLens server. Create a Neon branch/backup of your database. Keep your original Section 2 directory untouched.
2. Unzip Section 3 to a new folder. Copy the existing Section 2 `.env` **privately** to the new project root. Do not upload it or include it in a ZIP; preserve both Neon URLs and the persistent session secret.
3. Install dependencies within the new folder:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   cd frontend && npm ci && npm run build && cd ..
   ```
4. Run `python -m backend.database.schema_migrations upgrade` once, then `python -m backend.database.schema_migrations verify`. Expected auth revision: `auth_0003`; expected app revision: `app_0001`; both `up_to_date: true`.
5. Start with `node start.mjs`. If port 8000 belongs to another process, inspect it with `lsof -nP -iTCP:8000 -sTCP:LISTEN` and stop only the known old RepoLens server, or use `node start.mjs --backend-port 8001`.
6. Log in, open Settings, and verify API keys, devices and **Recent security activity**. Create and revoke a test key and confirm the actions appear without showing any secret in the audit list.
7. Confirm an invalid GitHub URL produces a safe 422 response; your regular `https://github.com/owner/repo` flow still works. Test public `/join` invitations on the actual built frontend.

## Four test disciplines (run from project root)

TDD RED→GREEN history is captured in the accompanying report. The source tests are committed to `tests/test_section3_security_tdd.py`.

```bash
# Unit and failure-first behavior
python -m pytest -q tests/test_section3_security_tdd.py

# Database and HTTP integration (isolated local test databases)
python -m pytest -q tests/test_section3_audit_integration.py

# Backend HTTP E2E and regression
python -m pytest -q tests/test_section2_api_e2e.py tests/test_section2_auth_tdd.py tests/test_section1_migrations.py

# Frontend unit and browser E2E (requires installed Vite/Playwright)
cd frontend
npm test
npx playwright install chromium
npm run test:browser -- e2e/section2_security.spec.js e2e/section3_security.spec.js
```

For a fully certified deployment, additionally test live Google and GitHub OAuth, HTTPS headers from your real domain, and real PostgreSQL with a **separate disposable Neon branch**. The repository's `tests/test_auth.py` includes mock-provider OAuth security coverage when `authlib` is installed.

## Security boundaries and remaining risks

- Audit records may contain user IDs and IP addresses; treat the database as sensitive, restrict operator access, and configure an organizational retention/deletion policy before public launch. No raw OAuth tokens, API keys, database credentials, or invite URLs are stored in the new audit records.
- Audit events for workspace/report/conversation mutations are written after successful route processing. If the audit store becomes unavailable at that moment, an operation could have committed before the request reports an error. Monitor DB availability and alert on HTTP 5xx. Production startup must apply migrations first.
- AI prompt-injection isolation is defense-in-depth; no textual prompt can guarantee zero injection risk. Never execute fetched repository code and continue validating cited evidence.
- `script-src 'self'` is strict; `style-src 'unsafe-inline'` remains for the current React styling. A future nonce/hashed style strategy would tighten this further.
- Invitation tokens are currently embedded in URLs; avoid access logging query strings and use `Referrer-Policy: no-referrer` on invitation pages. A fragment- or POST-based invitation design may be preferable for a large public deployment.
- User-facing validation returns HTTP 422 rather than the older 400 in some invalid-request cases. The UI already handles non-2xx responses.
