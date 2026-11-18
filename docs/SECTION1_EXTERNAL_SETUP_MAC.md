# Section 1 — External PostgreSQL Setup (Mac) — Subagent 2

**Goal:** switch existing RepoLens user accounts, sessions, chats, and workspace data to PostgreSQL **without losing them**. The source archive contains source code but not your private `.env`, OAuth session secret, report files, indexes, or existing SQLite databases. **Do not delete the original RepoLens folder.**

## Choose only one database location

- **A. PostgreSQL in Docker Desktop on your Mac (recommended first):** no Neon account, no public hosting or custom domain needed.
- **B. Hosted Neon PostgreSQL (optional):** create a Neon project; internet access, credentials, and an active database are required. Prefer this when you plan to deploy the backend online.

ChromaDB stays separate for vector embeddings. RAG index jobs, the model embedding cache, local source files, and exported reports are not automatically transferred to PostgreSQL. Preserve their storage folders as well.

## Preparation (do this for either A or B)

1. Stop the old RepoLens process with **Ctrl+C**. Stop scheduled workers too.
2. Back up your **entire current project folder**, especially the private `.env`, `.repolens_auth/` (including `secret.key`, `accounts.sqlite3`, `conversations.sqlite3` and job state), `.repolens_chroma/`, reports and caches. Keep that backup outside the new project and protect it because it contains credentials and user data. On an existing PostgreSQL installation, create a separate `pg_dump` backup as well.
3. Extract the updated ZIP to a **new** folder. Do not overwrite or discard the working project yet.
4. Restore your existing private `.env` and state directories to the new `RepoLens/` folder. Do not create a new session secret if you need existing logins to stay valid.
5. Open the **new** `RepoLens` folder in VS Code and open Terminal in that folder.
6. Prepare Python, using your existing virtual environment if it has dependencies installed:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

7. Confirm you are in the folder containing `requirements.txt` and `compose.postgres.yml`. Do not paste the contents of `.env` into chats, screenshots, GitHub or logs.

## Option A — Local PostgreSQL with Docker Desktop

### A1. Install Docker Desktop (one-time external setup, YOUR action)

1. Open https://docs.docker.com/desktop/setup/install/mac-install/
2. Select the installer for Apple silicon (M-series) or Intel as appropriate.
3. Install Docker Desktop and launch the application; accept any required on-device prompts.
4. Verify in Terminal:

```bash
docker --version
docker compose version
docker info
```

If `docker` is not found, complete the Docker Desktop setup and open a new terminal. If the daemon is unavailable, open Docker Desktop and let it initialize. Docker Desktop includes Compose.

### A2. Configure the local PostgreSQL password (YOUR action)

1. Generate a unique local password:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(24))'
```

2. Open your **private** root `.env`. Add these entries, substituting exactly the same generated password for both placeholders. URL-encode it if you choose a password containing special URL characters. The suggested `token_urlsafe` password avoids most URL-reserved characters:

```dotenv
REPOLENS_DB_PASSWORD=REPLACE_WITH_GENERATED_PASSWORD
REPOLENS_MIGRATION_TARGET_URL=postgresql+psycopg://repolens:REPLACE_WITH_GENERATED_PASSWORD@127.0.0.1:5432/repolens
REPOLENS_AUTH_DATABASE_URL=postgresql+psycopg://repolens:REPLACE_WITH_GENERATED_PASSWORD@127.0.0.1:5432/repolens
REPOLENS_DATABASE_URL=postgresql+psycopg://repolens:REPLACE_WITH_GENERATED_PASSWORD@127.0.0.1:5432/repolens
```

Do not use a production password for the local test database. Do not commit `.env`.

### A3. Start PostgreSQL (YOUR action)

```bash
docker compose --env-file .env -f compose.postgres.yml up -d
docker compose --env-file .env -f compose.postgres.yml ps
```

Wait for `database` to be **healthy**. If port 5432 is occupied by a different PostgreSQL server, stop the conflict or configure a different host port in the local compose file and connection string consistently. Never point the migration at an occupied unrelated database.

### A4. Move the old users and chats into the EMPTY database

**If this is a fresh installation without existing accounts or chats, skip the copy commands below and proceed directly to A5.**

First inspect counts without writing any destination records:

```bash
python -m backend.database.migrate_database --source .repolens_auth
```

Confirm the counts represent your old data. If it says no source databases, check the old `.repolens_auth` directory before proceeding. Then apply the **one-time** data copy:

```bash
python -m backend.database.migrate_database --source .repolens_auth --apply
```

This script refuses a destination containing existing user or application rows, copies from SQLite read-only, checks copied row counts, and leaves the original SQLite files untouched. If the destination is already populated, **do not delete or truncate it**: determine whether the migration already ran before doing anything else.

### A5. Apply the new Alembic schema versions

```bash
python -m backend.database.schema_migrations upgrade
python -m backend.database.schema_migrations verify
```

Expected: JSON entries for **auth** and **app** each with `up_to_date: true`. These are separate migration histories, even though both point to the same PostgreSQL database.

If `verify` fails, don't start the website. Preserve backups and inspect the error first. Never run `downgrade` on a database with user data; it explicitly refuses nonempty tables.

### A6. Verify database and website

```bash
python scripts/check_postgres.py
node start.mjs
```

`check_postgres.py` uses temporary test data, cleans it up, and verifies conversation/workspace operation. In a browser, sign into your **existing** account and check saved conversations, workspace members, pinned answers, checklist state and reports. Restart RepoLens and check them again. Test a second account if you have one.

Remember: RAG indexes remain in ChromaDB, not PostgreSQL. If you opened a brand new folder without copying local Chroma/report state, those will not appear until restored.

### A7. Back up the new PostgreSQL database

Keep periodic private SQL dumps. For example, while the Docker database is running:

```bash
docker compose --env-file .env -f compose.postgres.yml exec -T database pg_dump -U repolens -d repolens > repolens-postgres-backup.sql
```

The SQL dump contains private user data. Move it to encrypted backup storage, never to GitHub; delete any unencrypted temporary copies appropriately. Validate that a backup can be restored into a separate disposable database before relying on it.

## Option B — Neon-hosted PostgreSQL

### B1. Create a cloud account (YOUR action)

1. Open https://console.neon.tech/ and sign in / sign up.
2. Create a project such as `RepoLens`, select the closest suitable region to your eventual backend host, and create a PostgreSQL database. Use a **separate empty database or a fresh branch** for the first migration rehearsal; do not use a production database containing unrelated data.
3. In the project dashboard, select **Connect / Connection string** and choose a **direct** (non-pooled) connection for schema setup and the first deployment rehearsal. Pooled connections can be configured separately later.
4. Copy the connection string securely into your `.env` on your Mac, **not into chat**. A Neon URL commonly looks like this:

```dotenv
REPOLENS_MIGRATION_TARGET_URL=postgresql+psycopg://USERNAME:PASSWORD@HOSTNAME.neon.tech/DATABASE?sslmode=require
REPOLENS_AUTH_DATABASE_URL=postgresql+psycopg://USERNAME:PASSWORD@HOSTNAME.neon.tech/DATABASE?sslmode=require
REPOLENS_DATABASE_URL=postgresql+psycopg://USERNAME:PASSWORD@HOSTNAME.neon.tech/DATABASE?sslmode=require
```

If Neon provides `postgresql://` or `postgres://`, change **only the scheme** to `postgresql+psycopg://` for RepoLens's SQLAlchemy/psycopg configuration. Preserve the host, username, password, database and TLS query settings. If the password contains characters such as `@`, `:`, `/` or `#`, URL-encode it correctly. Prefer a verified TLS mode if supported by your client/environment.

### B2. Test connectivity without exposing credentials

```bash
python - <<'PY'
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
load_dotenv()
e = create_engine(os.environ['REPOLENS_MIGRATION_TARGET_URL'])
with e.connect() as db:
    print('PostgreSQL connection:', db.scalar(text('SELECT 1')))
e.dispose()
PY
```

Expected: `PostgreSQL connection: 1`.

### B3. Migrate and verify

Keep the old server stopped. If you have existing local data, run the dry run and then the one-time copy to your **empty** Neon database:

```bash
python -m backend.database.migrate_database --source .repolens_auth
python -m backend.database.migrate_database --source .repolens_auth --apply
```

For a fresh database without old records, skip the copy. In both cases, apply schema versions:

```bash
python -m backend.database.schema_migrations upgrade
python -m backend.database.schema_migrations verify
python scripts/check_postgres.py
```

The last command uses temporary records, but it must be run against a database **you are allowed to test**. Don't point destructive experiments or CI tests at your real data.

Then start RepoLens and verify old accounts and workspaces as with Option A. The Mac backend needs internet access to reach Neon. A cloud database doesn't automatically deploy your website; production hosting and OAuth callback configuration belong to Section 10.

## The four testing categories after setup

Once Python dependencies and Docker PostgreSQL are ready, run the dedicated Section 1 tests:

```bash
python -m pytest -q tests/test_section1_migrations.py tests/test_section1_cli.py tests/test_section1_database_e2e.py
```

For the **real PostgreSQL integration test**, create a separate throwaway PostgreSQL **test database** (not the database holding your real accounts), set `REPOLENS_TEST_POSTGRES_URL` to that connection string privately, then run:

```bash
python -m pytest -q tests/test_postgres_integration.py
```

Never point test URLs at production. The CI workflow already provides a dedicated PostgreSQL service and test schema.

For full website browser E2E and frontend build (these were not runnable in the implementation sandbox because frontend dependencies were not installed):

```bash
cd frontend
npm ci
npx playwright install chromium
npm run build
npm run test:browser
cd ..
```

Browser tests use Playwright and mock some API responses; also manually check your **real database-backed account**, chat persistence, and workspace after restart. **TDD** means tests were written first and first observed failing, then passed after code changes; it is a development approach, not a separate kind of external production test.

## What I need you to do, and what I can do

**You must:** install/run Docker Desktop or create a Neon project; hold the database credentials; back up your old private data; decide when to stop/restart the live server; verify your existing Google/GitHub login and saved records.

**Code work already provided:** two independent Alembic migration environments, immutable baseline schemas, data-preserving migration of existing tables, missing-column compatibility for legacy conversations, explicit version inspection, safe refusal to drop populated tables, CLI commands, automated tests, and production Docker startup migration wiring.

## If an error appears

- `docker: command not found`: Docker Desktop/CLI isn't installed or accessible.
- `Connection refused` on port 5432: container not healthy or wrong host/port.
- `password authentication failed`: check `.env` password. Updating the POSTGRES_PASSWORD variable **doesn't reset the password in an already-initialized Postgres volume**.
- `No source auth/chat databases found`: the old `.repolens_auth` folder was not copied or your custom `REPOLENS_AUTH_DIR` points elsewhere.
- `Destination must be empty`: stop; the target has rows. Do not clear it blindly.
- `Existing ... table is incompatible`: stop. Make a backup and inspect the schema; the migration intentionally refuses to silently rewrite unknown tables.
- `Missing module alembic/psycopg`: activate the correct `.venv` and rerun `pip install -r requirements.txt`.
- `Schema is not current`: run `schema_migrations upgrade` after backup; use `verify` again.
- OAuth login fails after changing folders: ensure the old `secret.key`, OAuth credentials, and browser origin settings were preserved. Don't regenerate secrets casually.

**Rollback without data loss:** Restore the **full** old project and its backed-up local SQLite/auth state if you haven't written new records to PostgreSQL yet. If you have written new records to PostgreSQL, take a fresh backup and plan a controlled reverse transfer rather than just switching `.env` back; new PostgreSQL-only data would otherwise disappear from the website. For database schema failures, restore a verified PostgreSQL backup into a separate database. Do not use `alembic downgrade` as a data recovery tool.
