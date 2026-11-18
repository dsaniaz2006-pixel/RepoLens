"""Alembic runner shared by independent auth and product schema histories."""
from sqlalchemy import create_engine, pool
from alembic import context


def run_migration_environment(metadata, kind):
    config = context.config
    url = config.attributes.get('database_url')
    if not url:
        raise RuntimeError('Use python -m backend.database.schema_migrations (credentials stay in .env).')
    version_table = 'alembic_version_' + kind
    if context.is_offline_mode():
        context.configure(url=url, target_metadata=metadata, literal_binds=True,
                          version_table=version_table, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = create_engine(url, poolclass=pool.NullPool, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=metadata,
                              version_table=version_table, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
