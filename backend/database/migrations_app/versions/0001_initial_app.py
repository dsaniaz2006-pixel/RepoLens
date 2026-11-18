"""Version current conversation and workspace tables and add legacy workspace_id.

Revision ID: app_0001
Revises:
"""
from alembic import op
from sqlalchemy import Column, String, inspect
from backend.database.schema_definitions import app_metadata
from backend.database.version_safety import create_missing_compatible_tables, assert_empty_tables

revision = 'app_0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    create_missing_compatible_tables(bind, app_metadata, allowed_missing={'conversations': {'workspace_id'}})
    cols = {column['name'] for column in inspect(bind).get_columns('conversations')}
    if 'workspace_id' not in cols:
        op.add_column('conversations', Column('workspace_id', String(36), nullable=True))


def downgrade():
    bind = op.get_bind()
    assert_empty_tables(bind, app_metadata)
    for table in reversed(app_metadata.sorted_tables):
        table.drop(bind, checkfirst=True)
