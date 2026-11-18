"""Offline, atomic migration of users/sessions/chats/product data to an empty database.

Stop the API first. Dry-run is the default. Source files are opened read-only;
source data is never deleted and existing destination rows are never overwritten.
"""
import argparse
import sqlite3
from pathlib import Path
from sqlalchemy import create_engine,MetaData,Table,select,func
from sqlalchemy.exc import SQLAlchemyError
from backend.database.conversations import metadata as chat_metadata
from backend.database.schema_definitions import auth_metadata
import backend.database.product_store as product_store  # registers product tables
from backend.auth.auth_database import AuthDatabase

AUTH_SCHEMA='''CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, provider TEXT NOT NULL, subject TEXT NOT NULL, name TEXT NOT NULL, email TEXT, created_at INTEGER NOT NULL, UNIQUE(provider,subject));
CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), csrf TEXT NOT NULL, expires_at INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);'''

def migrate(source_directory,target_url,*,apply=False):
    source=Path(source_directory).resolve();sources=[]
    for name in ('accounts.sqlite3','conversations.sqlite3'):
        path=source/name
        if not path.is_file():continue
        engine=create_engine('sqlite:///file:'+str(path)+'?mode=ro&uri=true')
        found=MetaData();found.reflect(bind=engine)
        sources.append((engine,found))
    if not sources:raise ValueError('No source auth/chat databases found')
    if not target_url.startswith(('postgresql+psycopg://','sqlite:///')):raise ValueError('Unsupported target URL')
    # Dry-run must not create tables or files in the destination.
    counts={}
    for engine,meta in sources:
        with engine.connect() as conn:
            for name,table in meta.tables.items():
                    if name in ('alembic_version_auth', 'alembic_version_app'):continue
                    counts[name]=conn.scalar(select(func.count()).select_from(table))
    if not apply:return {'applied':False,'counts':counts}
    target_auth=AuthDatabase(target_url)
    with target_auth.connect() as conn:conn.executescript(AUTH_SCHEMA)
    target=target_auth.engine;auth_metadata.create_all(target);chat_metadata.create_all(target)
    dest=MetaData();dest.reflect(bind=target)
    order=['users','sessions','session_devices','api_keys','login_attempts','audit_events','usage_counters','request_buckets','usage_events','user_plans','conversations','conversation_messages','product_items','checklist_shares','workspace_members','workspace_invites','used_workspace_invites','task_leases']
    if set(counts)-set(order):raise ValueError('Unknown source tables; migration stopped to avoid omitting data')
    with target.begin() as out:
        for name in order:
            if name in dest.tables and out.scalar(select(func.count()).select_from(dest.tables[name])):raise ValueError('Destination must be empty; no rows were migrated')
        for name in order:
            table=dest.tables.get(name)
            if table is None:continue
            for engine,meta in sources:
                if name not in meta.tables:continue
                with engine.connect() as inc:
                    rows=inc.execute(select(meta.tables[name])).mappings().all()
                # SQLite JSON reflects with the same JSON type; SQLAlchemy handles decoding.
                if rows:
                    values=[dict(row) for row in rows]
                    if name=='task_leases':values=[dict(row,token=None,lease_until=0) for row in values]
                    out.execute(table.insert(),values)
                assert out.scalar(select(func.count()).select_from(table))==counts.get(name,0)
    return {'applied':True,'counts':counts}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True);p.add_argument('--apply',action='store_true');args=p.parse_args()
    import os
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2]/'.env')
    target=os.getenv('REPOLENS_MIGRATION_TARGET_URL','')
    if not target:raise SystemExit('Set REPOLENS_MIGRATION_TARGET_URL; it is never printed')
    try:print(migrate(args.source,target,apply=args.apply))
    except (ValueError,SQLAlchemyError):raise SystemExit('Migration failed. Verify an empty destination and source permissions. Source data was not changed.')
