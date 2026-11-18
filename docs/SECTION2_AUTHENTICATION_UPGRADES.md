# RepoLens Section 2 — Authentication Upgrades

This change **extends the existing Google/GitHub OAuth + HTTPOnly cookie authentication**. It does not replace OAuth providers, RAG, ChromaDB, or the Section 1 Neon/PostgreSQL connection. It adds **three tables** in an additive Alembic auth migration (`auth_0002`): `api_keys`, `session_devices`, and `login_attempts`. User and session IDs remain unchanged.

## Before you install this project copy

1. Stop the running RepoLens server (`Ctrl+C`) and keep your current working Section 1 project folder unchanged as a rollback copy.
2. In Neon Console, create a separate database branch/snapshot for backup, or take a verified `pg_dump` backup. **Do not run destructive tests against your production branch.**
3. Extract the new Section 2 ZIP to a **new** directory. Copy your existing **private** root `.env` (the three Section 1 Neon database URLs and OAuth/Gemini settings) from your old project into the new directory. Do not upload `.env` to GitHub or this chat.
4. Copy persistent local data from your previous project as needed (such as `.repolens_auth`, `.repolens_cache`, reports, local RAG storage); PostgreSQL chat/auth records remain in Neon. The ZIP contains no private credentials or database records.
5. From the new project root, run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m backend.database.schema_migrations status
python -m backend.database.schema_migrations upgrade
python -m backend.database.schema_migrations verify
cd frontend && npm ci && npm run build && npm test && cd ..
node start.mjs
```

`auth.current` and `auth.head` must both be `auth_0002`; `app.current` and `app.head` should remain `app_0001`; both must report `schema_valid: true` and `up_to_date: true`. The upgrade creates new tables and **does not drop or rewrite users or sessions**. If anything fails, stop and investigate rather than deleting tables or rerunning SQLite-to-Neon transfer.

## What users see on the website

Open **Dashboard → Settings → Account security**. Create a named developer API key, copy it **once**, and store it privately. Refreshing the page never reveals its full value again. You can list/revoke keys and inspect signed-in sessions, including browser/device metadata for newly created sessions. Use **Sign out all devices** to invalidate every browser session for your account, including the current one. Existing older sessions may display unknown browser metadata because their records predate this update.

## Developer key API (server-side)

| Method | Endpoint | Auth | Description |
| --- | --- | --- | --- |
| GET | `/api/auth/keys` | Browser cookie | List **only your** active key labels, prefixes and timestamps |
| POST | `/api/auth/keys` | Browser cookie + CSRF | Create key (name 1–200 chars); return raw secret once |
| DELETE | `/api/auth/keys/{id}` | Browser cookie + CSRF | Revoke only your key |
| GET | `/api/auth/sessions` | Browser cookie | List your active sessions and current-device flag |
| DELETE | `/api/auth/sessions/all` | Browser cookie + CSRF | Revoke all your sessions, clear current cookie |

Application APIs (`/api/history`, `/api/conversations`, `/api/ask`, etc.) also accept `Authorization: Bearer rl_live_...` for CLI/script access. Bearer credentials bypass browser CSRF requirements **only** for these protected API routes; they never authorize `/api/auth/keys`, sessions management or dashboard page access. Invalid bearer tokens fail closed even if an unrelated valid cookie is also sent. Key secrets are SHA-256 hashed at rest and never included in listings. Maximum ten active keys per user.

For example, from your own Mac terminal (do **not** paste the token into chat or shell history):

```bash
# Fetch API key securely from a local secret store or protected environment variable.
curl -H "Authorization: Bearer $REPOLENS_PERSONAL_API_KEY" http://127.0.0.1:8000/api/history
```

Do not expose a local HTTP API beyond your own computer. Deployed access must use HTTPS.

## Suspicious sign-in protection

Failed OAuth callbacks count toward a 10-failure/15-minute IP-based window. During lockout, `/api/auth/login/{provider}` and `/api/auth/callback/{provider}` redirect to the login page with a readable message. A legitimate successful login clears the failure state. This is **not** a password lockout: Google and GitHub handle their own credential verification.

In production, `REPOLENS_TRUSTED_PROXY_NETWORKS` optionally identifies trusted reverse-proxy IP/CIDR ranges. The backend never trusts an incoming `X-Forwarded-For` header unless the connection is from a configured proxy. Configure it only if your proxy correctly sanitizes/appends the client address; never allow direct public access to the internal FastAPI port. This is distinct from Section 4's general API rate limiting.

## Acceptance testing

Use your existing configured local project, **not** production Neon for destructive testing.

```bash
python -m pytest -q tests/test_section2_auth_tdd.py tests/test_section2_api_e2e.py tests/test_section1_migrations.py tests/test_section1_database_e2e.py
cd frontend
npm test
npm run build
npx playwright install chromium
npm run test:browser -- e2e/section2_security.spec.js
```

For real PostgreSQL integration, supply `REPOLENS_TEST_POSTGRES_URL` pointing to a **disposable dedicated test database/branch**, and run:

```bash
python -m pytest -q tests/test_postgres_integration.py
```

The PostgreSQL integration suite creates and drops temporary schemas **within the test database**. Never configure this test URL with your production Neon connection string. Automated Playwright tests mock HTTP provider responses and **do not** prove real Google/GitHub OAuth consent or production HTTPS.

Finally, manually sign in using Google/GitHub, create and revoke a developer key, verify second-device login and logout, and restart the backend to confirm sessions and keys persist in Neon. Test the UI's light/dark theme and small screen layout.

## External setup

No new external provider or payment account is required. Your existing Neon, Google OAuth and GitHub OAuth settings are retained. Only if deploying to a new public domain do you need to update **authorized redirect URIs** in Google/GitHub developer consoles. Production deployment remains its own Section 10 acceptance gate.
