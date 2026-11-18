# RepoLens — Section 1 completion report / Subagent 1

Date: 2026-11-12

## Scope and design decisions

The Phase 11 release candidate already had SQLAlchemy conversation/workspace storage, an optional SQLAlchemy PostgreSQL auth adapter, and a one-shot migration utility. Replacing that code or redefining user IDs would risk breaking chats and OAuth sessions. Section 1 therefore adds **versioned schema management**, preserving existing interfaces and SQLite development defaults.

**Changes in this ZIP:**

- `backend/database/schema_definitions.py`: pinned 0001 baseline metadata for 2 auth tables and 8 application tables; independent of future ORM changes.
- `backend/database/migrations_auth/` and `migrations_app/`: separate Alembic environments and revision histories (`alembic_version_auth`, `alembic_version_app`), safe even when the same PostgreSQL database stores both.
- `backend/database/version_safety.py`: compatible-schema checks before adoption, legacy `conversations.workspace_id` backfill, missing safe indexes, and nonempty-data downgrade refusal.
- `backend/database/schema_migrations.py`: `status`, `upgrade`, `verify`, and guarded `downgrade`; reads secrets from private environment, never command-line arguments.
- `deployment/Dockerfile`: apply Alembic migrations before starting the production API.
- `requirements.txt`: explicit Alembic dependency.
- `tests/test_section1_migrations.py`, `tests/test_section1_cli.py`, `tests/test_section1_database_e2e.py`: tests-first specification, CLI integration, legacy data E2E and restart-style persistence coverage.
- `tests/test_postgres_integration.py`: CI's opt-in real PostgreSQL test now confirms both Alembic revisions with the migrated data still accessible.
- `docs/SECTION1_EXTERNAL_SETUP_MAC.md`: detailed Docker and Neon external setup.

**Important compatibility:** No RAG index files, public reports, OAuth secrets, or SQLite originals are removed or rewritten. Configured production PostgreSQL uses `REPOLENS_AUTH_DATABASE_URL` and `REPOLENS_DATABASE_URL`. Existing local SQLite setup remains supported.

## Four verification disciplines

| Discipline | What was exercised | Local result |
|---|---|---|
| Test-driven development (RED → GREEN) | Auth/app schema contracts first failed during import of missing module; implementation followed | RED captured, GREEN 12 passed |
| Unit tests | Independent versioning, schema validation, old-column upgrade, safe rollback, auth SQL adapter | Passed |
| Integration tests | CLI subprocess status/upgrade/verify, SQLAlchemy persistence, offline SQLite copy and reopening migrated data | Passed |
| End-to-end tests | **Database-path E2E:** original SQLite accounts + chat + workspace → offline migration → versioned destination → reopened persistent records | Passed |

**Local measured result:** 12 passed, 1 skipped (`REPOLENS_TEST_POSTGRES_URL` not configured). Python compilation passed.

**Not verified in this container:** Real PostgreSQL service (Docker/psycopg unavailable), full FastAPI/OAuth or Vite browser E2E (missing third-party dependencies and frontend npm modules). The ZIP includes the real PostgreSQL integration test; it should run in GitHub Actions with its PostgreSQL service and also on your Mac if you provide a *separate test database*.

**Do not call Section 1 production-certified until:** local/mac PostgreSQL migration applied to your verified backup, two real accounts tested, backed-up source data verified, restart persistence checked, and CI full frontend/browser suites passing.

## Operator commands

Run from repo root in a virtual environment:

```bash
python -m backend.database.schema_migrations status
python -m backend.database.schema_migrations upgrade
python -m backend.database.schema_migrations verify
```

If migrating existing SQLite state, **stop the API and workers** and first run:

```bash
python -m backend.database.migrate_database --source .repolens_auth
python -m backend.database.migrate_database --source .repolens_auth --apply
```

Only after checking the copied counts and backup should you run the schema upgrade and the application.

## Why auth and app have separate migration history

The preexisting RepoLens code supports one URL for auth and another for conversations/workspaces. A single Alembic version table would break when both URLs point to the same database or to separate databases. Independent `auth_0001` and `app_0001` revisions work in both cases and do not force disruptive changes to the OAuth and workspace SQL call sites.

## Safe rollback policy

Database migration revisions intentionally refuse `downgrade` if any managed table contains rows. Safe rollback is restore-from-backup in a controlled maintenance window. The source SQLite files are not deleted by `migrate_database.py`.
