"""Add verified OAuth transactional email outbox (no user/session rewrites).

Revision ID: auth_0005
Revises: auth_0004
"""
from alembic import op
from sqlalchemy import inspect, select, func
from backend.database.schema_definitions import login_email_notifications

revision = 'auth_0005'
down_revision = 'auth_0004'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    login_email_notifications.create(bind, checkfirst=True)
    for index in login_email_notifications.indexes:
        index.create(bind, checkfirst=True)


def downgrade():
    bind = op.get_bind()
    if inspect(bind).has_table('login_email_notifications'):
        if bind.scalar(select(func.count()).select_from(login_email_notifications)):
            raise RuntimeError('Refusing to remove saved email delivery events; restore a backup instead.')
        login_email_notifications.drop(bind, checkfirst=True)
