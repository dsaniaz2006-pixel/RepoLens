"""Offline database end-to-end: old SQLite -> copy -> Alembic -> reopened data.

This is storage E2E, not a browser/OAuth/hosted-Postgres acceptance test.
"""
import hashlib
import sqlite3

from sqlalchemy import create_engine, text
from backend.database.conversations import ConversationStore
from backend.database.product_store import workspace, role
from backend.database.migrate_database import migrate
from backend.database.schema_migrations import upgrade_databases, migration_status


def test_existing_user_session_chat_and_workspace_survive_full_offline_migration(tmp_path):
    old = tmp_path / 'old_auth'
    old.mkdir()
    original_auth = old / 'accounts.sqlite3'
    with sqlite3.connect(original_auth) as db:
        db.executescript('''
            CREATE TABLE users (id TEXT PRIMARY KEY, provider TEXT NOT NULL,
              subject TEXT NOT NULL, name TEXT NOT NULL, email TEXT,
              created_at INTEGER NOT NULL, UNIQUE(provider,subject));
            CREATE TABLE sessions (token_hash TEXT PRIMARY KEY,
              user_id TEXT NOT NULL REFERENCES users(id), csrf TEXT NOT NULL,
              expires_at INTEGER NOT NULL);
            INSERT INTO users VALUES ('account-1','github','123','Existing account',
              'existing@example.test',100);
            INSERT INTO sessions VALUES ('previously-issued-hash','account-1',
              'existing-csrf',9999999999);
        ''')
    source = ConversationStore('sqlite:///' + str(old / 'conversations.sqlite3'))
    chat = source.create('account-1', 'pallets/flask', 'a' * 40)
    _, lease, _ = source.begin('account-1', chat['id'], 'pallets/flask', 0)
    source.finish(chat['id'], lease, 0, 'Where does it start?',
                  {'answer':'See the source file','citations':[{'path':'app.py','start_line':1,'end_line':2}],'uncertain':False})
    ws = workspace(source.engine, 'account-1', 'Engineering')
    source.engine.dispose()

    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in old.glob('*.sqlite3')}
    target = 'sqlite:///' + str(tmp_path / 'upgraded.sqlite3')
    preview = migrate(old, target)
    assert not preview['applied'] and not (tmp_path / 'upgraded.sqlite3').exists()
    transferred = migrate(old, target, apply=True)
    assert transferred['counts']['users'] == 1
    assert transferred['counts']['conversation_messages'] == 2
    assert transferred['counts']['workspace_members'] == 1
    versioned = upgrade_databases(target, target)
    assert all(value['up_to_date'] for value in versioned.values())

    # Simulates re-opening the website on the following day after a restart.
    reopened = ConversationStore(target)
    restored = reopened.get('account-1', chat['id'])
    assert restored['version'] == 2
    assert [m['content'] for m in restored['messages']] == ['Where does it start?', 'See the source file']
    assert role(reopened.engine, ws, 'account-1') == 'owner'
    with create_engine(target).connect() as c:
        assert c.scalar(text("SELECT name FROM users WHERE id='account-1'")) == 'Existing account'
        assert c.scalar(text("SELECT csrf FROM sessions WHERE token_hash='previously-issued-hash'")) == 'existing-csrf'
    assert all(hashlib.sha256((old / name).read_bytes()).hexdigest() == digest for name,digest in before.items())
    assert all(v['up_to_date'] for v in migration_status(target, target).values())
