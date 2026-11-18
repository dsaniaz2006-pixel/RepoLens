"""Read-only Section 1 acceptance check for the configured online PostgreSQL DB.

Run from repository root:
  python scripts/verify_section1_neon.py --source repolens_backup/.repolens_auth

No database credentials, names/emails, user IDs, or session hashes are printed.
No tables, rows, migration history or local files are modified.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.database.schema_definitions import auth_metadata, app_metadata
from backend.database.schema_migrations import configured_urls, migration_status

REQUIRED_AUTH = ('users', 'sessions')
REQUIRED_APP = (
    'conversations', 'conversation_messages', 'product_items',
    'workspace_members', 'workspace_invites', 'checklist_shares',
    'used_workspace_invites', 'task_leases',
)
PRESERVE_IDENTITIES = {
    'users': ('id',),
    'conversations': ('id',),
    'conversation_messages': ('id',),
    'product_items': ('id',),
    'workspace_members': ('workspace', 'user'),
}


def _sqlite_backup(path: Path) -> tuple[dict[str, int], dict[str, set[tuple]]]:
    """Read a backed-up SQLite file in true read-only mode, never create it."""
    if not path.is_file():
        raise FileNotFoundError('Source backup is missing: ' + path.name)
    counts: dict[str, int] = {}
    identities: dict[str, set[tuple]] = {}
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        allowed = set(REQUIRED_AUTH) | set(REQUIRED_APP)
        for name in sorted(tables & allowed):
            counts[name] = int(connection.execute('SELECT count(*) FROM "' + name + '"').fetchone()[0])
            if name in PRESERVE_IDENTITIES:
                columns = ', '.join('"' + column + '"' for column in PRESERVE_IDENTITIES[name])
                identities[name] = set(connection.execute('SELECT ' + columns + ' FROM "' + name + '"'))
    finally:
        connection.close()
    return counts, identities


def _target_audit(url: str, required: tuple[str, ...]) -> tuple[str, dict[str, int], dict[str, set[tuple]], list[str]]:
    """Read-only server-side schema and row checks; no personal data in results."""
    engine = create_engine(url, pool_pre_ping=True, connect_args={'connect_timeout': 10} if make_url(url).get_backend_name() == 'postgresql' else {})
    counts: dict[str, int] = {}
    identities: dict[str, set[tuple]] = {}
    missing: list[str] = []
    try:
        with engine.connect() as connection:
            database = str(connection.scalar(text('SELECT current_database()'))) if make_url(url).get_backend_name() == 'postgresql' else 'SQLite test database'
            available = set(inspect(connection).get_table_names())
            for name in required:
                if name not in available:
                    missing.append(name)
                    continue
                counts[name] = int(connection.scalar(text('SELECT count(*) FROM "' + name + '"')))
                if name in PRESERVE_IDENTITIES:
                    columns = ', '.join('"' + column + '"' for column in PRESERVE_IDENTITIES[name])
                    identities[name] = set(connection.execute(text('SELECT ' + columns + ' FROM "' + name + '"')).all())
        return database, counts, identities, missing
    finally:
        engine.dispose()


def audit(auth_url: str, app_url: str, source: Path, *, allow_sqlite_for_tests: bool = False) -> dict[str, Any]:
    if not allow_sqlite_for_tests:
        for url in (auth_url, app_url):
            if make_url(url).drivername != 'postgresql+psycopg':
                raise ValueError('Auth and application URLs must use PostgreSQL + psycopg (check .env)')

    source = Path(source)
    auth_file = source / 'accounts.sqlite3'
    app_file = source / 'conversations.sqlite3'
    src_auth_count, src_auth_ids = _sqlite_backup(auth_file)
    src_app_count, src_app_ids = _sqlite_backup(app_file)
    original_counts = src_auth_count | src_app_count
    original_ids = src_auth_ids | src_app_ids

    auth_db, auth_counts, auth_ids, missing_auth = _target_audit(auth_url, REQUIRED_AUTH)
    app_db, app_counts, app_ids, missing_app = _target_audit(app_url, REQUIRED_APP)
    target_counts = auth_counts | app_counts
    target_ids = auth_ids | app_ids

    checks: dict[str, Any] = {}
    for name, source_count in original_counts.items():
        if name in ('task_leases', 'sessions'):
            # A background job lease or login session may be removed after migration.
            continue
        checks[name] = {
            'source_rows': source_count,
            'target_rows': target_counts.get(name, 0),
            'preserved': (original_ids[name] <= target_ids.get(name, set())) if name in original_ids
                         else target_counts.get(name, 0) >= source_count,
        }
    versions = migration_status(auth_url, app_url)
    schema_ok = not (missing_auth or missing_app) and all(v['up_to_date'] for v in versions.values())
    data_ok = all(v['preserved'] for v in checks.values())
    return {
        'pass': bool(schema_ok and data_ok),
        'connected': True,
        'database_names': {'auth': auth_db, 'app': app_db},
        'migration_versions': versions,
        'missing_tables': {'auth': missing_auth, 'app': missing_app},
        'row_counts': {'backup': original_counts, 'online': target_counts},
        'preservation_checks': checks,
        'manual_live_checks_remaining': [
            'Sign in with an existing Google/GitHub account and ensure it is the same user',
            'Create a conversation, refresh/restart RepoLens, and ensure its messages persist',
            'Create a workspace, refresh/restart RepoLens, and ensure membership persists',
            'Verify the actual web server uses PostgreSQL rather than an old SQLite process',
            'Run the browser E2E suite and real PostgreSQL tests on a separate test database',
        ],
        'notes': [
            'This tool does not modify Neon, source SQLite, or any session.',
            'Sessions and in-progress task leases change naturally and are not strict equality checks.',
            'index_jobs.sqlite3 is backed up but is not transferred by migrate_database.py.',
            'If the backup contains no chats/workspaces, live chat/workspace persistence cannot be inferred from historical rows.',
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='repolens_backup/.repolens_auth', help='Directory with original backed-up SQLite files')
    args = parser.parse_args()
    try:
        auth_url, app_url = configured_urls()
        result = audit(auth_url, app_url, ROOT / args.source)
    except Exception as exc:
        # Never print engine exceptions, because they can contain the connection URL/password.
        print(json.dumps({'pass': False, 'error_type': type(exc).__name__, 'hint':
                          'Check original backup, database URLs, psycopg package, and Neon access. Keep exception details private.'}, indent=2))
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
