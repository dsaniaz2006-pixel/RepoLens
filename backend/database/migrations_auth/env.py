from backend.database.schema_definitions import auth_metadata
from backend.database.migrations_common import run_migration_environment
run_migration_environment(auth_metadata, 'auth')
