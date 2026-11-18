# RepoLens Section 1 — Online Neon PostgreSQL Setup (macOS)

**Objective:** Store RepoLens users, sessions, chats, and workspaces in **online PostgreSQL hosted by Neon**. Keep your existing source code, current login identities, saved messages and RAG data safe.

**What I can provide:** PostgreSQL-compatible code, Alembic schema history, migration utility, automated tests, and this guide. **What you must do:** own the Neon account, configure the private connection string, stop/start your Mac server, keep a secure backup, and verify your real account. An uploaded source ZIP does not contain your private user data.

## Before you begin — important facts

- Neon is **online database hosting**, not website hosting. Your RepoLens website can still run via `node start.mjs` on your Mac while connecting to the online database. Putting the website on a public URL belongs to Section 10.
- PostgreSQL holds **accounts, sessions, chat history, workspaces and product records**. **ChromaDB** still holds RAG embeddings. Local report exports, embedding caches, index job state and filesystem content are **not transferred** by this database migration.
- **Do not share** connection strings or `.env` contents in chat, GitHub, screenshots, or tickets. The PostgreSQL password embedded in a URL grants database access.
- **Do not delete** your old RepoLens directory, `.repolens_auth/`, `.repolens_chroma/`, or your current `.env`. They are your fallback.
- A database backup is essential even if Neon provides branches/restore; the original local SQLite files must remain available throughout the change.

## Part A — Create the hosted database (YOU, outside ChatGPT)

1. Open **https://console.neon.tech/** in your browser. Sign in or create a Neon account. Use the **Free** plan if its current limits cover your project.
2. Click **New Project / Create Project** (label may differ). Set project name to **RepoLens**. The default PostgreSQL database is often named `neondb`; you may choose `repolens` if offered.
3. Select the region **closest to the backend that will connect to Neon**. While the backend runs on your Mac, choose the nearest suitable region offered. When you eventually deploy RepoLens, ideally host its backend near the database.
4. Create the project. Make a **development/testing branch** or a **separate empty test project/database** for rehearsals. Do **not** connect experiments to an existing production database.
5. In the Neon dashboard locate **Connect / Connection details**, select your intended branch and database, and **disable pooled connection** to copy the **direct** connection URL for the first migration. Direct mode is simpler for Alembic DDL. You can evaluate pooled connections later.
6. Your private URL looks *similar to* `postgresql://ROLE:PASSWORD@EP-ENDPOINT.REGION.neon.tech/neondb?sslmode=require` (illustrative only; never use it literally).
7. Copy the URL to a local secure password manager temporarily. Neon requires TLS; keep `sslmode=require`. If the console provides stronger certificate-verification options compatible with your Mac/Python runtime, use those for production.
8. Neon has a SQL Editor: you can later check tables and query `SELECT COUNT(*) FROM users;` without posting credentials anywhere. **Don't delete/edit application tables manually.**

Official references: https://neon.com/docs/connect/connect-from-any-app ; https://neon.com/docs/get-started-with-neon/signing-up ; https://neon.com/docs/introduction/branching

## Part B — Prepare the new RepoLens source on your Mac (YOU)

1. Open Finder → Downloads. Extract **RepoLens_Section1_PostgreSQL_Alembic_TDD_2026-11-12.zip** into a **new** folder. Don't overwrite your currently working RepoLens.
2. Shut down your old RepoLens process: in its Terminal press **Control+C**. Ensure other RepoLens worker or API processes are also stopped before copying databases.
3. Make a backup copy of the **entire current working project folder** to a private location. Include `.env` (hidden file), `.repolens_auth/` (accounts/chat SQLite, `secret.key`), ChromaDB and report directories, and any custom data folders. Confirm the backup can be opened.
4. Copy your old private `.env` and all relevant data directories into the **new** `RepoLens/` directory, preserving original names and permissions. In particular, preserve `secret.key` so old sessions remain verifiable.
5. In VS Code open the **new** `RepoLens` folder, then Terminal → New Terminal. Check `pwd` points at the folder with `requirements.txt` and `start.mjs`.
6. Prepare Python:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

For frontend preparation (as needed):

```bash
cd frontend
npm ci
cd ..
```

## Part C — Enter your Neon URL privately (YOU)

1. In VS Code find root **`.env`**, not `.env.example`. You can enable **View → Show Hidden Files** in Finder if necessary. The `.env` should be excluded from Git.
2. Keep all previous Google/GitHub/Gemini variables unchanged. **Add or update the following three variables** using the *same* **direct** Neon URL:

```dotenv
REPOLENS_MIGRATION_TARGET_URL=postgresql+psycopg://ROLE:URL_ENCODED_PASSWORD@HOST.neon.tech/neondb?sslmode=require
REPOLENS_AUTH_DATABASE_URL=postgresql+psycopg://ROLE:URL_ENCODED_PASSWORD@HOST.neon.tech/neondb?sslmode=require
REPOLENS_DATABASE_URL=postgresql+psycopg://ROLE:URL_ENCODED_PASSWORD@HOST.neon.tech/neondb?sslmode=require
```

3. Copy your **actual** URL from Neon, but change the URL prefix from `postgres://` or `postgresql://` to **`postgresql+psycopg://`**. Do *not* manually alter the host, username, password, database name or SSL query parameters. URLs with reserved characters in passwords must use URL-encoded passwords. If unsure, rotate the DB password to a URL-safe random one in the Neon console.
4. **Never paste the actual URL here.** If you need help, share only a screenshot with the password, username, URL and project ID fully hidden.

Why three variables? This RepoLens release candidate uses separate configurable auth and app stores; all three must point to the same intended Neon database for the one-time SQLite → online migration.

## Part D — Verify online connection (NO data changes)

From the RepoLens project root with `.venv` active:

```bash
python - <<'PY'
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
load_dotenv()
url = os.environ['REPOLENS_MIGRATION_TARGET_URL']
engine = create_engine(url, pool_pre_ping=True)
with engine.connect() as db:
    print('Connected:', db.scalar(text('SELECT 1')))
    print('Database server:', db.scalar(text('SELECT version()')).split(' on ')[0])
engine.dispose()
PY
```

Expected: `Connected: 1` and a PostgreSQL version string. This verifies your **Mac → online Neon** connection. It does **not** mean old account data has migrated.

If it fails: check internet/DNS, `.venv`, Python `psycopg` installation, branch selection, `sslmode=require`, password, and optional Neon IP-allow settings. Do not paste your full error if it contains a secret URI.

## Part E — Transfer your existing RepoLens data (IMPORTANT)

1. Keep the old API/worker stopped. Only run this against the **chosen EMPTY Neon destination**.
2. Run the **dry-run** first:

```bash
python -m backend.database.migrate_database --source .repolens_auth
```

3. Review the reported counts (`users`, `sessions`, `conversations`, `conversation_messages`, `workspace_members`, etc.). If your old chats/users were expected but counts show zero, **STOP**: confirm you copied the right `.repolens_auth/` folder or the path from `REPOLENS_AUTH_DIR`.
4. If the counts match your old project and the destination is empty, perform the one-time copy:

```bash
python -m backend.database.migrate_database --source .repolens_auth --apply
```

5. The tool reads SQLite in read-only mode, preserves original files, refuses populated targets and checks row counts. Do **not** run it repeatedly or delete Neon tables if it tells you the target is already populated.
6. If you are starting from an entirely **fresh account with no old SQLite data**, **skip the copy** and continue to the schema upgrade.

## Part F — Apply & verify Alembic schema versions (CODE PROVIDED)

```bash
python -m backend.database.schema_migrations status
python -m backend.database.schema_migrations upgrade
python -m backend.database.schema_migrations verify
```

Expected output (details may vary): both `auth` and `app` report `up_to_date: true`. This ZIP uses two independent Alembic histories so auth and app data can coexist in one Neon database without version-table collisions.

**Safety:** Only run `upgrade` after backing up your data. Do not use Alembic `downgrade` to recover user data. For failure recovery, restore a verified backup into a separate database or return to the untouched old folder *before any new cloud-only writes*.

## Part G — Run the website and verify from the user's perspective

1. With your `.env` set to Neon and the schema verified, start the **new** RepoLens:

```bash
node start.mjs
```

2. Open the local URL printed by the launcher; your browser frontend still runs on your Mac, but accounts and chats are stored **online in Neon**.
3. Log in with the **same Google/GitHub identity** as before. Verify saved conversations and messages, workspace membership and pinned answers. Test on two different accounts if possible.
4. Restart the backend; reopen the website and verify the same data is still visible.
5. In the Neon SQL Editor, inspect tables named `users`, `sessions`, `conversations`, `conversation_messages`, `workspace_members`, `alembic_version_auth`, `alembic_version_app`. Check non-sensitive row counts.
6. Remember: if RAG indexes disappear, check your original `.repolens_chroma/` and cache paths; PostgreSQL migration does not transfer ChromaDB.

## Part H — The four tests (what's real, what's still pending)

- **TDD**: tests were authored before implementation; captured RED and GREEN evidence is supplied. This is a development technique, not a remote-service pass.
- **Unit tests**: independent schema versions, legacy compatibility, rollback protections, auth SQL adapter.
- **Integration tests**: CLI status/upgrade/verify; migration and persistence. To run the **real PostgreSQL** test, use a **separate empty Neon test branch/database**, not your live accounts.
- **End-to-end**: local automated tests cover the storage journey (old SQLite → transfer → Alembic → reopened records). **Browser-level OAuth/Neon E2E still requires your Mac / CI and real credentials.**

First run local focused tests:

```bash
python -m pytest -q tests/test_section1_migrations.py tests/test_section1_cli.py tests/test_section1_database_e2e.py
```

For the opt-in PostgreSQL integration test, create a **throwaway Neon branch/database** and place `REPOLENS_TEST_POSTGRES_URL` in your private `.env` with its direct `postgresql+psycopg://...` URL. Then load the environment before pytest without echoing secrets:

```bash
python - <<'PY'
from dotenv import load_dotenv
import pytest
load_dotenv('.env')
raise SystemExit(pytest.main(['-q','tests/test_postgres_integration.py']))
PY
```

Never use your production Neon database in automated test commands.

For browser regression checks (requires Node dependencies and Playwright Chromium):

```bash
cd frontend
npm ci
npx playwright install chromium
npm run build
npm run test:browser
cd ..
```

In addition, verify **live login + persisted conversations + workspace permissions after restart** manually. Mocked browser tests alone do not prove Neon integration.

## Part I — Backup and recovery

- Before migration: preserve the working **old** project, private SQLite databases, `.env` and `secret.key`.
- After migration: maintain Neon backups or branch snapshots according to your plan's current retention; periodically create logical Postgres dumps via `pg_dump` from a trusted client and test restoration into a disposable database.
- Do not publish dumps or connection strings in GitHub. Use a password manager or protected environment-variable facility.
- If there are **new writes to Neon**, switching the app back to old SQLite without reverse migration loses those new records. Stop new writes and plan reconciliation first.

## What I need from you (not secrets)

1. Confirmation you've created the Neon project and a **separate test branch/database**.
2. Connection smoke result only: **`Connected: 1`** or a redacted error message.
3. Dry-run migration row counts (just table names + numbers, no personal data).
4. Schema verification: both `auth` and `app` say `up_to_date: true`.
5. Confirmation that old chats and Google/GitHub logins survive a restart.

**No credit card, Stripe, custom domain, or production hosting is required for Section 1.** Neon account creation and holding its private credentials are the only essential external pieces for an online database.
