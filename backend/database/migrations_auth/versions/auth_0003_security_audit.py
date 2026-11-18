"""Add append-only security audit events without changing existing auth rows.

Revision ID: auth_0003
Revises: auth_0002
"""
from alembic import op
from sqlalchemy import select, func, inspect
from backend.database.schema_definitions import audit_events

revision = 'auth_0003'
down_revision = 'auth_0002'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    audit_events.create(bind, checkfirst=True)
    for index in audit_events.indexes:
        index.create(bind, checkfirst=True)


def downgrade():
    bind = op.get_bind()
    if inspect(bind).has_table('audit_events'):
        if bind.scalar(select(func.count()).select_from(audit_events)):
            raise RuntimeError('Refusing to delete audit history; restore from backup instead.')
        audit_events.drop(bind, checkfirst=True)
