"""Guard Alembic baseline adoption and prevent accidental data-destructive rollback."""
from sqlalchemy import inspect, select, func


def create_missing_compatible_tables(bind, metadata, *, allowed_missing=None):
    allowed_missing = allowed_missing or {}
    inspector = inspect(bind)
    for table in metadata.sorted_tables:
        if inspector.has_table(table.name):
            actual = {column['name'] for column in inspector.get_columns(table.name)}
            expected = set(table.c.keys())
            missing = expected - actual - allowed_missing.get(table.name, set())
            if missing:
                raise RuntimeError(f'Existing {table.name} table is incompatible: missing columns {sorted(missing)}. Back up and investigate before upgrading.')
            expected_pk = {column.name for column in table.primary_key.columns}
            actual_pk = set(inspector.get_pk_constraint(table.name).get('constrained_columns') or [])
            if actual_pk != expected_pk:
                raise RuntimeError(f'Existing {table.name} table is incompatible: primary key mismatch. Back up and investigate before upgrading.')
            unique_sets = [set(row.get('column_names') or []) for row in inspector.get_unique_constraints(table.name)]
            unique_sets += [set(row.get('column_names') or []) for row in inspector.get_indexes(table.name) if row.get('unique')]
            for constraint in table.constraints:
                if constraint.__class__.__name__ == 'UniqueConstraint':
                    expected_unique = {col.name for col in constraint.columns}
                    if expected_unique not in unique_sets:
                        raise RuntimeError(f'Existing {table.name} table is incompatible: unique constraint missing. Back up and investigate before upgrading.')
    # No drops, renames or rewrites. Existing data is kept byte-for-byte.
    for table in metadata.sorted_tables:
        table.create(bind, checkfirst=True)
    for table in metadata.sorted_tables:
        for index in table.indexes:
            index.create(bind, checkfirst=True)


def assert_empty_tables(bind, metadata):
    inspector = inspect(bind)
    for table in metadata.sorted_tables:
        if inspector.has_table(table.name):
            if bind.scalar(select(func.count()).select_from(table)):
                raise RuntimeError(f'Refusing to downgrade non-empty table {table.name}; use a verified backup/restore instead.')
