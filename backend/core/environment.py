"""Read the app environment from the project root, independent of cwd.

Only the local .env file is loaded; a file in config/ is documentation,
not an implicit secret source. Process variables always take precedence.
"""
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / '.env'


def load_project_environment() -> bool:
    """Load a developer's private .env without overriding process settings."""
    return bool(load_dotenv(dotenv_path=ENV_FILE, override=False))
