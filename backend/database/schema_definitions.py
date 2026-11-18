"""Pinned Section 1 baseline schemas for Alembic revision 0001.

Keep these separate from current ORM tables. Future schema changes belong in new
Alembic revisions, not edits to previously deployed migration definitions.
"""
from sqlalchemy import (
    MetaData, Table, Column, Text, String, Integer, Float, JSON, ForeignKey,
    UniqueConstraint, Index,
)

auth_metadata = MetaData()
users = Table(
    'users', auth_metadata,
    Column('id', Text, primary_key=True),
    Column('provider', Text, nullable=False),
    Column('subject', Text, nullable=False),
    Column('name', Text, nullable=False),
    Column('email', Text),
    Column('created_at', Integer, nullable=False),
    UniqueConstraint('provider', 'subject'),
)
sessions = Table(
    'sessions', auth_metadata,
    Column('token_hash', Text, primary_key=True),
    Column('user_id', Text, ForeignKey('users.id'), nullable=False),
    Column('csrf', Text, nullable=False),
    Column('expires_at', Integer, nullable=False),
)
Index('sessions_expiry', sessions.c.expires_at)

# Freeze the original auth schema used by Alembic revision auth_0001.
# Never modify deployed revision definitions when adding new authentication controls.
auth_baseline_metadata = MetaData()
for _old_table in auth_metadata.sorted_tables:
    _old_table.to_metadata(auth_baseline_metadata)

api_keys = Table(
    'api_keys', auth_metadata,
    Column('id', String(32), primary_key=True),
    Column('user_id', Text, ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
    Column('key_hash', String(64), unique=True, nullable=False),
    Column('key_prefix', String(18), nullable=False),
    Column('name', String(200), nullable=False),
    Column('created_at', Integer, nullable=False),
    Column('last_used_at', Integer),
    Column('revoked', Integer, nullable=False, server_default='0'),
)
Index('api_keys_user_idx', api_keys.c.user_id)
session_devices = Table(
    'session_devices', auth_metadata,
    Column('token_hash', Text, ForeignKey('sessions.token_hash', ondelete='CASCADE'), primary_key=True),
    Column('ip_address', String(45)),
    Column('user_agent', String(200)),
    Column('created_at', Integer, nullable=False),
)
login_attempts = Table(
    'login_attempts', auth_metadata,
    Column('ip_address', String(45), primary_key=True),
    Column('fail_count', Integer, nullable=False),
    Column('window_started', Integer, nullable=False),
    Column('locked_until', Integer),
)

audit_events = Table(
    'audit_events', auth_metadata,
    Column('id', String(32), primary_key=True),
    Column('user_id', Text),  # nullable for failed logins; retained after account removal
    Column('action', String(64), nullable=False),
    Column('target', String(120)),  # only allowlisted opaque IDs, never URLs/tokens
    Column('ip_address', String(45)),
    Column('created_at', Integer, nullable=False),
)
Index('audit_events_user_idx', audit_events.c.user_id, audit_events.c.created_at)

# Append-only Section 4 limits. Auth and application tables may share one Neon
# database while retaining separate Alembic version histories.
usage_counters = Table(
    'usage_counters', auth_metadata,
    Column('user_id', Text, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('action', String(16), primary_key=True),
    Column('window_start', Integer, primary_key=True),
    Column('count', Integer, nullable=False),
)
request_buckets = Table(
    'request_buckets', auth_metadata,
    Column('identity_hash', String(64), primary_key=True),
    Column('action', String(16), primary_key=True),
    Column('window_start', Integer, primary_key=True),
    Column('count', Integer, nullable=False),
)
usage_events = Table(
    'usage_events', auth_metadata,
    Column('id', String(32), primary_key=True),
    Column('user_id', Text, ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
    Column('action', String(16), nullable=False),
    Column('created_at', Integer, nullable=False),
)
Index('usage_events_user_date', usage_events.c.user_id, usage_events.c.created_at)
user_plans = Table(
    'user_plans', auth_metadata,
    Column('user_id', Text, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('plan', String(12), nullable=False),
)

# Optional OAuth transactional email outbox. The welcome notification is
# deduplicated per provider-owned user id, while every return login has its
# own opaque event identifier. No tokens, message bodies or passwords stored.
login_email_notifications = Table(
    'login_email_notifications', auth_metadata,
    Column('id', String(32), primary_key=True),
    Column('user_id', Text, ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
    Column('dedupe_key', String(100), unique=True, nullable=False),
    Column('kind', String(16), nullable=False),
    Column('status', String(12), nullable=False),
    Column('created_at', Integer, nullable=False),
    Column('sent_at', Integer),
    Column('attempts', Integer, nullable=False, server_default='0'),
    Column('next_retry_at', Integer, nullable=False, server_default='0'),
    Column('claimed_until', Integer),
)
Index('login_email_notifications_pending', login_email_notifications.c.status,
      login_email_notifications.c.next_retry_at)

app_metadata = MetaData()
conversations = Table(
    'conversations', app_metadata,
    Column('id', String(36), primary_key=True),
    Column('owner', String(128), index=True, nullable=False),
    Column('repository', String(256), nullable=False),
    Column('revision', String(40), nullable=False),
    Column('workspace_id', String(36)),
    Column('title', String(120), nullable=False),
    Column('updated', Float, nullable=False),
    Column('version', Integer, nullable=False),
    Column('lease', String(36)),
    Column('lease_until', Float),
)
conversation_messages = Table(
    'conversation_messages', app_metadata,
    Column('id', String(36), primary_key=True),
    Column('conversation_id', String(36), index=True, nullable=False),
    Column('position', Integer, nullable=False),
    Column('role', String(16), nullable=False),
    Column('content', Text, nullable=False),
    Column('citations', JSON, nullable=False),
    Column('uncertain', Integer, nullable=False),
)
product_items = Table(
    'product_items', app_metadata,
    Column('id', String(36), primary_key=True),
    Column('owner', String(128), index=True, nullable=False),
    Column('kind', String(30), index=True, nullable=False),
    Column('data', JSON, nullable=False),
    Column('updated', Float, nullable=False),
)
workspace_members = Table(
    'workspace_members', app_metadata,
    Column('workspace', String(36), primary_key=True),
    Column('user', String(128), primary_key=True),
    Column('role', String(12), nullable=False),
)
workspace_invites = Table(
    'workspace_invites', app_metadata,
    Column('hash', String(64), primary_key=True),
    Column('workspace', String(36), nullable=False),
    Column('expires', Float, nullable=False),
)
checklist_shares = Table(
    'checklist_shares', app_metadata,
    Column('checklist_id', String(36), primary_key=True),
    Column('token_hash', String(64), unique=True, nullable=False),
    Column('created', Float, nullable=False),
)
used_workspace_invites = Table(
    'used_workspace_invites', app_metadata,
    Column('hash', String(64), primary_key=True),
    Column('used_at', Float, nullable=False),
)
task_leases = Table(
    'task_leases', app_metadata,
    Column('name', String(80), primary_key=True),
    Column('token', String(36)),
    Column('lease_until', Float, nullable=False),
)
