# RepoLens Section 4 — Rate Limiting and Usage Quotas

This release builds on the working Section 3 security project and its **Neon PostgreSQL** setup. Keep your original Section 3 folder and its private `.env` unchanged as a rollback reference. No new provider or database is required.

## Website behavior

- Home and Settings now display **Your AI usage** with actual `/api/usage` counters, remaining requests, and a Refresh button.
- Default account plan is **Free**. Daily UTC allowances: Analyze 5, Ask 20, Index 2. Pro: 50/500/20. Team: 200/2000/100.
- Hourly per-IP caps: Analyze 10, Ask 60, Index 5. Shared public networks can encounter these caps even if an individual account has allowance left.
- Daily quotas reset at **00:00 UTC** (05:30 IST). Hourly buckets reset at the beginning of each UTC hour.
- A 429 response includes a safe explanatory message and `Retry-After`. The browser stays signed in. API client errors surface the message.
- An expensive request is **reserved before the GitHub/Gemini operation starts**. Malformed or provider-failed attempts can therefore use allowance. Polling job progress, loading reports, and accessing Settings do not cost an AI action.
- IPs are stored as keyed hashes; secret tokens, GitHub URLs and request bodies are not stored in usage events.
- The browser cannot change account plans. The `user_plans` database table is reserved for verified future billing/admin workflows. Membership in a Team workspace does not itself create a paid Team subscription.

## Actions metered

| Action | HTTP endpoints |
| --- | --- |
| Analyze | `/api/analyze`, `/api/interview`, `/api/contribution`, `/api/diff`, `/api/security-scan`, `/api/flow`, `/api/checklists` |
| Ask | `/api/ask`, `/api/local/repositories/{id}/ask` |
| Index | `/api/index`, `/api/index/jobs`, `/api/local/index` |

All are `POST`; reading `/api/usage` is unrestricted by the paid AI budget but **requires authentication**. An expired/revoked API key cannot spend requests. Rate limits are stored in the auth PostgreSQL database and shared by backend processes; no Redis is necessary for your current architecture.

## Safely update your existing Neon project

1. In Neon Console, make a **recovery branch** or an independently verified backup of your current `production` branch. Keep the original Section 3 ZIP and your local SQLite backups.
2. Stop the old RepoLens server (Ctrl+C). If port 8000 remains occupied, identify the owner first with `lsof -nP -iTCP:8000 -sTCP:LISTEN`. Do not terminate an unrelated process.
3. Extract the new Section 4 ZIP into a *new directory*. Open that extracted folder in VS Code; don't overwrite your working Section 3 folder.
4. Copy your existing private Section 3 root `.env` **locally** into the new project's root. Check that `REPOLENS_AUTH_DATABASE_URL` and `REPOLENS_DATABASE_URL` still point to your Neon DB. Do **not** send those URLs to ChatGPT or commit `.env`.
5. Prepare dependencies (only on first setup):

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   cd frontend && npm ci && cd ..
   ```
6. After the Neon backup is confirmed, run the **additive** database migration:

   ```bash
   python -m backend.database.schema_migrations upgrade
   python -m backend.database.schema_migrations verify
   ```

   Expected: `auth.current` and `auth.head` both `auth_0004`, `auth.schema_valid` and `auth.up_to_date` true; `app.current` remains `app_0001`. The migration adds `usage_counters`, `request_buckets`, `usage_events`, and `user_plans`, preserving all existing users, chats, sessions, and audit logs.
7. Verify frontend and start:

   ```bash
   cd frontend && npm run build && npm test && cd ..
   node start.mjs
   ```

8. Sign in to the **new** RepoLens website. Home and Settings should show usage counts. Make **one real or controlled test** analysis; then click Refresh. It should increment by one. Refresh the page; it should stay incremented because counters are on Neon. Do not intentionally exhaust all your production credits just to prove limits.

## Automated tests (do not write synthetic test data to production Neon)

Run locally, offline for the focused SQLite/SQLAlchemy tests:

```bash
python -m pytest -q tests/test_section4_limits_red.py tests/test_section4_tdd.py tests/test_section4_http_integration.py
cd frontend
npm test
npm run test:browser -- e2e/section4_usage.spec.js
cd ..
```

**Real PostgreSQL test:** Create a **disposable separate Neon test branch/database** or use Docker's local integration-test PostgreSQL. Set `REPOLENS_TEST_POSTGRES_URL` only in that separate test context, then run:

```bash
python -m pytest -q tests/test_section4_postgres_integration.py
```

The test creates **and drops** an isolated schema. It must **never** receive your production connection string or database. The GitHub Actions workflow already supplies an isolated PostgreSQL service and runs the new tests in CI.

**Full browser suite:** With frontend dependencies and Chromium installed, run `cd frontend && npx playwright install chromium && npm run test:browser`. Browser tests use intercepted API calls; they do not test real Gemini/OAuth nor live Neon. Live functional acceptance must still be performed separately on your Mac.

## Technical design and safety

- Both account daily and IP hourly counters are reserved **in one transaction** via conditional SQL upserts. Any rejected reservation rolls back both counters, including concurrent requests.
- The counters are keyed by authenticated user ID (daily UTC) and HMAC(IP) (UTC hourly). Usage events are stored server-side for future analysis.
- The API returns `503` rather than invoking Gemini if usage storage is unavailable (fail closed).
- `Retry-After` tells clients when the current limiting window resets. Usage is not user-resettable by refreshing browsers or creating more API keys.
- All database modifications are in migration `auth_0004`; previous Alembic revisions are unchanged. Downgrading populated usage tables is intentionally blocked—restore a verified backup or roll forward instead.
- Legacy SQLite-to-PostgreSQL copy utility was updated so usage tables are not silently omitted.

## Final acceptance checklist

- [ ] Neon `auth_0004` migration verified
- [ ] Existing Google/GitHub login, chat, reports, workspaces and Section 3 audit log work
- [ ] `/api/usage` is authenticated, shows Free plan usage and does not expose private IPs or keys
- [ ] Home and Settings display correct usage and persist it across refresh and restart
- [ ] Quota limit produces 429 without executing expensive functions (verified in HTTP integration tests)
- [ ] Cookie and Bearer-token requests spend the **same user's** quota
- [ ] Concurrent quota tests pass on a **disposable real PostgreSQL** database
- [ ] Playwright browser test passes on Mac
- [ ] All earlier Section 3 security/browser tests still pass

If the new tables are not yet migrated, AI write routes safely fail with HTTP 503. Apply and verify the migration before public use. Report only redacted errors; never send database URLs, API keys or raw browser session cookies.
