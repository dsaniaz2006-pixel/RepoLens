"""TDD for read-only migration acceptance; never calls a live external database."""
import sqlite3

from backend.database.conversations import ConversationStore
from backend.database.migrate_database import migrate
from backend.database.schema_migrations import upgrade_databases
from scripts.verify_section1_neon import audit


def _seed(tmp_path):
    source = tmp_path / 'original'
    source.mkdir()
    with sqlite3.connect(source / 'accounts.sqlite3') as connection:
        connection.executescript('''
            CREATE TABLE users (id TEXT PRIMARY KEY, provider TEXT NOT NULL, subject TEXT NOT NULL,
              name TEXT NOT NULL, email TEXT, created_at INTEGER NOT NULL, UNIQUE(provider,subject));
            CREATE TABLE sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL,
              csrf TEXT NOT NULL, expires_at INTEGER NOT NULL);
            INSERT INTO users VALUES ('user1', 'github', '0001', 'Private', 'private@example.test', 10);
            INSERT INTO sessions VALUES ('session-hash', 'user1', 'csrf-secret', 9999999999);
        ''')
    chat = ConversationStore('sqlite:///' + str(source / 'conversations.sqlite3'))
    row = chat.create('user1', 'pallets/flask', 'a' * 40)
    _, token, _ = chat.begin('user1', row['id'], 'pallets/flask', 0)
    chat.finish(row['id'], token, 0, 'Where?', {'answer': 'Code', 'citations': [], 'uncertain': False})
    chat.engine.dispose()
    target = 'sqlite:///' + str(tmp_path / 'destination.db')
    assert migrate(source, target, apply=True)['applied']
    upgrade_databases(target, target)
    return source, target


def test_verified_online_equivalent_never_exposes_private_identity(tmp_path):
    source, target = _seed(tmp_path)
    result = audit(target, target, source, allow_sqlite_for_tests=True)
    assert result['pass'] is True
    assert result['preservation_checks']['users']['preserved'] is True
    assert result['preservation_checks']['conversations']['preserved'] is True
    assert result['preservation_checks']['conversation_messages']['preserved'] is True
    assert result['row_counts']['online']['conversation_messages'] == 2
    assert 'private@example.test' not in str(result)
    assert 'session-hash' not in str(result)


def test_missing_original_user_is_detected_even_when_target_has_same_row_count(tmp_path):
    source, target = _seed(tmp_path)
    from sqlalchemy import create_engine, text
    engine = create_engine(target)
    with engine.begin() as c:
        c.execute(text("UPDATE users SET id='different' WHERE id='user1'"))
    engine.dispose()
    result = audit(target, target, source, allow_sqlite_for_tests=True)
    assert result['pass'] is False
    assert result['preservation_checks']['users']['preserved'] is False


def test_live_database_requirement_rejects_unintended_local_sqlite(tmp_path):
    source, target = _seed(tmp_path)
    import pytest
    with pytest.raises(ValueError, match='PostgreSQL'):
        audit(target, target, source)
