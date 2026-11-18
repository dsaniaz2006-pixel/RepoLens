# Section 1 — Local verification evidence (2026-11-12)

## Red phase (TDD)

- Created `tests/test_section1_migrations.py` before the migration implementation: collection failed with `ModuleNotFoundError: backend.database.schema_migrations` (expected RED).
- Added a regression for a deleted table when the Alembic version is still current: it failed (`assert True is False`) before adding structural verification (expected RED).

## Green phase (executed in the current sandbox)

```text
python -m pytest -q tests/test_section1_migrations.py tests/test_section1_cli.py tests/test_section1_database_e2e.py tests/test_postgres_integration.py
............s    [100%]
12 passed, 1 skipped
```

Skipped: actual PostgreSQL service integration because `REPOLENS_TEST_POSTGRES_URL` was not configured in this environment. The same test is wired into GitHub Actions with a PostgreSQL 17 service.

## Existing database regression tests (executed)

```text
python -m pytest -q tests/test_conversations.py -k 'ownership or expired'
.. [100%]
2 passed, 5 deselected

python -m pytest -q tests/test_product_upgrade.py -k 'workspace_invite_single_use_and_access or private_results_cannot_be_read_by_team_member'
.. [100%]
2 passed, 22 deselected
```

Total locally observed passing cases: **16**. No failing checks in the selected runnable scope.

## Scope caveats

- The migration-path E2E validates a full storage transfer and reopened records; it does not simulate the entire website in a browser.
- The current sandbox lacks Docker, Authlib, psycopg, Google GenAI SDK, Chromadb, and frontend npm modules; full backend+frontend, browser Playwright, and live PostgreSQL tests **were not executed** here.
- The source ZIP includes tests for real PostgreSQL migration in CI. Operator must verify local/hosted PostgreSQL and real accounts before calling Section 1 fully complete.
- Source `.env`, database files, keys, and snapshots are excluded from the delivery ZIP.
