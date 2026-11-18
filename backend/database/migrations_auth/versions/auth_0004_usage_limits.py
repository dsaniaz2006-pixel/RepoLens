"""Add atomic usage/rate windows and usage events (no existing rows changed).

Revision ID: auth_0004
Revises: auth_0003
"""
from alembic import op
from sqlalchemy import inspect, select, func
from backend.database.schema_definitions import usage_counters, request_buckets, usage_events, user_plans

revision = 'auth_0004'
down_revision = 'auth_0003'
branch_labels = None
depends_on = None

TABLES = (usage_counters, request_buckets, usage_events, user_plans)

def upgrade():
    connection=op.get_bind()
    for table in TABLES:
        table.create(connection,checkfirst=True)
        for index in table.indexes:
            index.create(connection,checkfirst=True)

def downgrade():
    connection=op.get_bind()
    inspector=inspect(connection)
    for table in reversed(TABLES):
        if inspector.has_table(table.name):
            if connection.scalar(select(func.count()).select_from(table)):
                raise RuntimeError('Cannot downgrade non-empty usage and billing tables; restore a backup instead.')
            table.drop(connection,checkfirst=True)
