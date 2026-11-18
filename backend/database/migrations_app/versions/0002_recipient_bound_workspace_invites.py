"""Add optional verified-recipient email hashes to existing invitations.

Revision ID: app_0002
Revises: app_0001
"""
from alembic import op
from sqlalchemy import Column, String, inspect, text

revision='app_0002'
down_revision='app_0001'
branch_labels=None
depends_on=None


def upgrade():
    bind=op.get_bind()
    columns={entry['name'] for entry in inspect(bind).get_columns('workspace_invites')}
    if 'recipient_email_hash' not in columns:
        op.add_column('workspace_invites',Column('recipient_email_hash',String(64),nullable=True))


def downgrade():
    # Allow only disposable, empty databases to downgrade. Never remove a
    # recipient restriction from an existing invitation.
    bind=op.get_bind()
    count=bind.scalar(text('SELECT COUNT(*) FROM workspace_invites'))
    if count:
        raise RuntimeError('Refusing to downgrade non-empty workspace_invites; restore a verified backup instead.')
    with op.batch_alter_table('workspace_invites') as batch:
        batch.drop_column('recipient_email_hash')
