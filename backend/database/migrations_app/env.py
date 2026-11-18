from backend.database.conversations import metadata as app_metadata
import backend.database.product_store  # registers all workspace/product tables for future autogenerate
from backend.database.migrations_common import run_migration_environment
run_migration_environment(app_metadata, 'app')
