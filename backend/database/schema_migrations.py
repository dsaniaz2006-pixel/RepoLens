"""Safe, independent Alembic migrations for RepoLens's auth and product stores.

Use: python -m backend.database.schema_migrations status|upgrade|downgrade
Passwords are read from .env (never accepted on the CLI or printed).
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url
from alembic.config import Config
from alembic import command
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from backend.database.schema_definitions import auth_metadata, app_metadata
from backend.database.version_safety import assert_empty_tables

ROOT = Path(__file__).resolve().parents[2]


def _config(kind: str, url: str) -> Config:
    if kind not in ('auth', 'app'):
        raise ValueError('Unknown schema')
    config = Config()
    config.set_main_option('script_location', str(Path(__file__).resolve().parent / ('migrations_' + kind)))
    config.attributes['database_url'] = url
    return config


def _current(url: str, kind: str) -> str | None:
    # Inspecting an uninitialized local database must not create an empty file.
    parsed = make_url(url)
    if parsed.get_backend_name() == 'sqlite' and parsed.database not in (None, ':memory:'):
        if not Path(parsed.database).exists():
            return None
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            if not inspect(connection).has_table('alembic_version_' + kind):
                return None
            return MigrationContext.configure(connection, opts={'version_table':'alembic_version_' + kind}).get_current_revision()
    finally:
        engine.dispose()


def _schema_valid(url: str, metadata) -> bool:
    parsed = make_url(url)
    if parsed.get_backend_name() == 'sqlite' and parsed.database not in (None, ':memory:'):
        if not Path(parsed.database).exists():
            return False
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            for table in metadata.sorted_tables:
                if not inspector.has_table(table.name):
                    return False
                columns = {column['name'] for column in inspector.get_columns(table.name)}
                if not set(table.c.keys()).issubset(columns):
                    return False
                pk = set(inspector.get_pk_constraint(table.name).get('constrained_columns') or [])
                if pk != {column.name for column in table.primary_key.columns}:
                    return False
            # app_0001 deliberately uses a frozen schema. Validate additive
            # Section 6 columns separately without editing deployed history.
            if metadata is app_metadata:
                invites = {col['name'] for col in inspector.get_columns('workspace_invites')}
                if 'recipient_email_hash' not in invites:
                    return False
            return True
    finally:
        engine.dispose()


def migration_status(auth_url: str, app_url: str) -> dict:
    result = {}
    for kind, url, metadata in [('auth', auth_url, auth_metadata), ('app', app_url, app_metadata)]:
        head = ScriptDirectory.from_config(_config(kind, url)).get_current_head()
        current = _current(url, kind)
        schema_valid = _schema_valid(url, metadata)
        result[kind] = {'current': current, 'head': head, 'schema_valid': schema_valid,
                        'up_to_date': current == head and schema_valid}
    return result


def upgrade_databases(auth_url: str, app_url: str) -> dict:
    # Both histories are independent, even when the URLs point at the same DB.
    for kind, url in [('auth', auth_url), ('app', app_url)]:
        parsed = make_url(url)
        if parsed.get_backend_name() == 'sqlite' and parsed.database not in (None, ':memory:'):
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
        command.upgrade(_config(kind, url), 'head')
    return migration_status(auth_url, app_url)


def downgrade_databases(auth_url: str, app_url: str) -> dict:
    # Downgrade is for EMPTY, disposable test DBs only; never a data rollback plan.
    for kind, url, metadata in [('auth', auth_url, auth_metadata), ('app', app_url, app_metadata)]:
        engine = create_engine(url, pool_pre_ping=True)
        try:
            with engine.connect() as connection:
                assert_empty_tables(connection, metadata)
        finally:
            engine.dispose()
    for kind, url in [('app', app_url), ('auth', auth_url)]:
        command.downgrade(_config(kind, url), 'base')
    return migration_status(auth_url, app_url)


def configured_urls() -> tuple[str, str]:
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env', override=False)
    folder = Path(os.getenv('REPOLENS_AUTH_DIR', str(ROOT / '.repolens_auth'))).resolve()
    auth_url = os.getenv('REPOLENS_AUTH_DATABASE_URL') or 'sqlite:///' + str(folder / 'accounts.sqlite3')
    app_url = os.getenv('REPOLENS_DATABASE_URL') or 'sqlite:///' + str(folder / 'conversations.sqlite3')
    for url in (auth_url, app_url):
        parsed = make_url(url)
        if parsed.drivername not in ('sqlite', 'pysqlite', 'postgresql+psycopg'):
            raise ValueError('Only SQLite or PostgreSQL (psycopg) database URLs are supported.')
    return auth_url, app_url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('status', 'upgrade', 'verify', 'downgrade'))
    parser.add_argument('--allow-empty-downgrade', action='store_true',
                        help='Only use in disposable test databases. Refuses non-empty tables.')
    args = parser.parse_args()
    if args.action == 'downgrade' and not args.allow_empty_downgrade:
        parser.error('Downgrade disabled by default. Use backups for real rollback.')
    auth_url, app_url = configured_urls()
    if args.action == 'upgrade':
        result = upgrade_databases(auth_url, app_url)
    elif args.action == 'downgrade':
        result = downgrade_databases(auth_url, app_url)
    else:
        result = migration_status(auth_url, app_url)
    print(json.dumps(result, indent=2))  # Never display database URLs or credentials.
    if args.action == 'verify' and not all(section['up_to_date'] for section in result.values()):
        raise SystemExit('Database schema is not current. Back up, then run schema_migrations upgrade.')


if __name__ == '__main__':
    main()
