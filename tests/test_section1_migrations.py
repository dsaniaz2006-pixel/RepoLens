"""Section 1 TDD acceptance tests: independent schema versions and safe data upgrades."""
from pathlib import Path
import sqlite3
import pytest
from sqlalchemy import create_engine, inspect, text

from backend.database.schema_migrations import upgrade_databases, migration_status, downgrade_databases


def urls(tmp_path):
    return ('sqlite:///' + str(tmp_path / 'accounts.sqlite3'),
            'sqlite:///' + str(tmp_path / 'conversations.sqlite3'))


def test_tdd_fresh_databases_receive_independent_alembic_versions(tmp_path):
    auth_url, app_url = urls(tmp_path)
    before = migration_status(auth_url, app_url)
    assert not Path(tmp_path / 'accounts.sqlite3').exists()
    assert before['auth']['current'] is None and before['app']['current'] is None
    upgraded = upgrade_databases(auth_url, app_url)
    assert upgraded['auth']['current'] == upgraded['auth']['head']
    assert upgraded['app']['current'] == upgraded['app']['head']
    with create_engine(auth_url).connect() as connection:
        assert connection.scalar(text('SELECT count(*) FROM alembic_version_auth')) == 1
    with create_engine(app_url).connect() as connection:
        assert connection.scalar(text('SELECT count(*) FROM alembic_version_app')) == 1
    assert {'users','sessions'}.issubset(inspect(create_engine(auth_url)).get_table_names())
    assert {'conversations', 'conversation_messages', 'product_items', 'workspace_members',
            'workspace_invites','used_workspace_invites','checklist_shares','task_leases'}.issubset(
                inspect(create_engine(app_url)).get_table_names())


def test_tdd_same_database_url_has_both_migration_branches(tmp_path):
    auth_url, _ = urls(tmp_path)
    status = upgrade_databases(auth_url, auth_url)
    assert status['auth']['current'] == status['auth']['head']
    assert status['app']['current'] == status['app']['head']
    assert status == upgrade_databases(auth_url, auth_url)


def test_tdd_legacy_auth_rows_and_sessions_survive_versioning(tmp_path):
    auth_url, app_url = urls(tmp_path)
    with sqlite3.connect(tmp_path / 'accounts.sqlite3') as db:
        db.executescript('''CREATE TABLE users(id TEXT PRIMARY KEY,provider TEXT NOT NULL,subject TEXT NOT NULL,
          name TEXT NOT NULL,email TEXT,created_at INTEGER NOT NULL,UNIQUE(provider,subject));
          CREATE TABLE sessions(token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),
          csrf TEXT NOT NULL, expires_at INTEGER NOT NULL);
          INSERT INTO users VALUES('u1','github','123','Existing','a@example.com',100);
          INSERT INTO sessions VALUES('hash1','u1','csrf1',9999999999);''')
    upgrade_databases(auth_url, app_url)
    with create_engine(auth_url).connect() as c:
        assert c.scalar(text("SELECT name FROM users WHERE id='u1'")) == 'Existing'
        assert c.scalar(text("SELECT user_id FROM sessions WHERE token_hash='hash1'")) == 'u1'


def test_tdd_old_chat_table_gets_workspace_column_without_deleting_rows(tmp_path):
    auth_url, app_url = urls(tmp_path)
    with sqlite3.connect(tmp_path / 'conversations.sqlite3') as db:
        db.executescript('''CREATE TABLE conversations(id VARCHAR(36) PRIMARY KEY,owner VARCHAR(128) NOT NULL,
        repository VARCHAR(256) NOT NULL,revision VARCHAR(40) NOT NULL,title VARCHAR(120) NOT NULL,
        updated FLOAT NOT NULL,version INTEGER NOT NULL,lease VARCHAR(36),lease_until FLOAT);
        INSERT INTO conversations VALUES('chat1','alice','o/r','abc','Old chat',1.0,0,NULL,NULL);''')
    upgrade_databases(auth_url, app_url)
    with create_engine(app_url).connect() as c:
        assert c.scalar(text("SELECT title FROM conversations WHERE id='chat1'")) == 'Old chat'
        assert c.scalar(text("SELECT workspace_id FROM conversations WHERE id='chat1'")) is None


def test_tdd_downgrade_refuses_to_drop_user_data(tmp_path):
    auth_url, app_url = urls(tmp_path)
    upgrade_databases(auth_url, app_url)
    with create_engine(auth_url).begin() as c:
        c.execute(text("INSERT INTO users VALUES('u1','github','123','Existing',NULL,100)"))
    with pytest.raises(RuntimeError,match='non-empty'):
        downgrade_databases(auth_url, app_url)
    with create_engine(auth_url).connect() as c:
        assert c.scalar(text("SELECT count(*) FROM users")) == 1


def test_tdd_incompatible_existing_table_is_rejected_not_marked_current(tmp_path):
    auth_url, app_url = urls(tmp_path)
    with sqlite3.connect(tmp_path / 'accounts.sqlite3') as c:
        c.execute('CREATE TABLE users(id TEXT PRIMARY KEY)')
    with pytest.raises(RuntimeError, match='incompatible'):
        upgrade_databases(auth_url, app_url)
    assert migration_status(auth_url, app_url)['auth']['current'] is None


def test_tdd_empty_disposable_downgrade_is_allowed(tmp_path):
    auth_url, app_url = urls(tmp_path)
    upgrade_databases(auth_url, app_url)
    status = downgrade_databases(auth_url, app_url)
    assert status['auth']['current'] is None and status['app']['current'] is None
    assert 'users' not in inspect(create_engine(auth_url)).get_table_names()
    assert 'conversations' not in inspect(create_engine(app_url)).get_table_names()


def test_tdd_auth_adapter_can_write_and_revoke_after_alembic(tmp_path):
    from backend.auth.auth_database import AuthDatabase
    auth_url, app_url = urls(tmp_path)
    upgrade_databases(auth_url, app_url)
    adapter = AuthDatabase(auth_url)
    with adapter.connect() as conn:
        conn.execute('INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)',
                     ('u7', 'github', 'abc', 'Tester', None, 1234))
        conn.execute('INSERT INTO sessions VALUES (?, ?, ?, ?)', ('tok', 'u7', 'csrf', 99999))
    with adapter.connect() as conn:
        assert conn.execute('SELECT user_id FROM sessions WHERE token_hash=?', ('tok',)).fetchone()['user_id'] == 'u7'
        conn.execute('DELETE FROM sessions WHERE token_hash=?', ('tok',))
    with adapter.connect() as conn:
        assert conn.execute('SELECT user_id FROM sessions WHERE token_hash=?', ('tok',)).fetchone() is None


def test_tdd_verify_catches_deleted_table_even_with_current_revision(tmp_path):
    auth_url, app_url = urls(tmp_path)
    upgrade_databases(auth_url, app_url)
    with create_engine(app_url).begin() as c:
        c.execute(text('DROP TABLE task_leases'))
    assert migration_status(auth_url, app_url)['app']['up_to_date'] is False
