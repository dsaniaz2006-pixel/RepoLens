"""Version the existing user and session tables without discarding any records.

Revision ID: auth_0001
Revises:
"""
from alembic import op
from sqlalchemy import inspect, select, func
from backend.database.schema_definitions import auth_baseline_metadata
from backend.database.version_safety import create_missing_compatible_tables, assert_empty_tables

revision = 'auth_0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    create_missing_compatible_tables(op.get_bind(), auth_baseline_metadata)


def downgrade():
    bind = op.get_bind()
    assert_empty_tables(bind, auth_baseline_metadata)
    for table in reversed(auth_baseline_metadata.sorted_tables):
        table.drop(bind, checkfirst=True)
