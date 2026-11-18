"""API key, session metadata and login-abuse storage. Additive; no existing rows modified.

Revision ID: auth_0002
Revises: auth_0001
"""
from alembic import op
from sqlalchemy import inspect, select, func
from backend.database.schema_definitions import api_keys, session_devices, login_attempts

revision = 'auth_0002'
down_revision = 'auth_0001'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    for table in (api_keys, session_devices, login_attempts):
        table.create(bind, checkfirst=True)
    for index in api_keys.indexes:
        index.create(bind, checkfirst=True)


def downgrade():
    bind = op.get_bind()
    for table in (api_keys, session_devices, login_attempts):
        if inspect(bind).has_table(table.name):
            if bind.scalar(select(func.count()).select_from(table)):
                raise RuntimeError(f'Refusing to drop non-empty {table.name}; back up and restore instead.')
    for table in (login_attempts, session_devices, api_keys):
        table.drop(bind, checkfirst=True)
