"""Shared, easy-to-tune configuration for RepoLens."""
import os

GITHUB_API_BASE = "https://api.github.com"
REQUEST_TIMEOUT = 20
# Compatibility alias for the original Stage 1 implementation.
REQUEST_TIMEOUT_SECONDS = REQUEST_TIMEOUT

# Gemini model specified by the October 2026 build guide.
GEMINI_MODEL = "gemini-3.5-flash-lite"

# Context limits are character limits, not token limits. They make the first
# version predictable and reduce accidental large API requests.
MAX_FILES = 20
MAX_FILE_CHARS = 8_000
# Backwards-compatible alias used by the original Stage 2B implementation.
MAX_CHARS_PER_FILE = MAX_FILE_CHARS
TOTAL_CONTEXT_BUDGET = 30_000
TREE_CONTEXT_BUDGET = 8_000
MAX_ANALYSIS_PROMPT_CHARS = 60_000
MAX_ANALYSIS_REQUEST_CHARS = 70_000
INDEX_FORMAT_VERSION = "4"
# Preserve half the source-text budget for implementation files.
MIN_SOURCE_CONTEXT_CHARS = 15_000

# GitHub Contents API may omit the file body for larger files. Skip those
# before requesting their contents when the tree reports a size.
GITHUB_CONTENTS_MAX_BYTES = 1_000_000
MAX_FALLBACK_TREE_ENTRIES = 5_000

# Bounds for the documented fallback used when a recursive tree is truncated.
FALLBACK_SOURCE_DIRS = {
    "src", "lib", "app", "pkg", "packages", "backend", "frontend",
    "api", "core", "server", "client", "web",
}

SKIP_DIR_NAMES = {
    ".git", "node_modules", "vendor", "dist", "build", "coverage",
    ".venv", "venv", "env", "__pycache__", ".next", ".nuxt", ".ssh",
    ".aws", ".azure", ".gcloud",
    "target", "out", "bower_components", ".mypy_cache", ".ruff_cache",
}

SKIP_FILE_NAMES = {
    ".env", ".npmrc", ".pypirc", ".netrc", "credentials.json",
    "credential.json", "secrets.json", "secret.json", "token.json", "auth.json",
    "terraform.tfstate", "terraform.tfstate.backup", "id_rsa", "id_dsa",
    "id_ecdsa", "id_ed25519", "known_hosts", "package-lock.json",
    "pnpm-lock.yaml", "npm-shrinkwrap.json", "yarn.lock", "cargo.lock",
    "poetry.lock", "pipfile.lock", "composer.lock", "gemfile.lock",
}

SKIP_EXTENSIONS = {
    ".lock", ".pem", ".key", ".p12", ".pfx", ".p7b", ".p7c", ".jks",
    ".keystore", ".crt", ".cer", ".der", ".asc", ".gpg", ".ppk",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf",
    ".woff", ".woff2", ".ttf", ".eot", ".zip", ".gz", ".tar", ".tgz",
    ".7z", ".rar", ".exe", ".dll", ".so", ".dylib", ".bin", ".wasm",
    ".mp3", ".mp4", ".mov", ".avi", ".sqlite", ".db",
}

# RAG settings (separate from the small report-context budget).
CHUNK_SIZE_CHARS = 1500
CHUNK_OVERLAP_CHARS = 200
# Grounded chat uses a slightly wider evidence window than a one-function lookup.
# Configure this independently of the indexing profile. Bound the value so an
# accidental large setting cannot send enormous untrusted source into the model.
try:
    RAG_TOP_K = int(os.getenv('REPOLENS_RAG_TOP_K', '8'))
except ValueError as exc:
    raise ValueError('REPOLENS_RAG_TOP_K must be an integer from 1 to 12') from exc
if not 1 <= RAG_TOP_K <= 12:
    raise ValueError('REPOLENS_RAG_TOP_K must be an integer from 1 to 12')
EMBEDDING_MODEL = 'gemini-embedding-2'
CHROMA_PATH = os.environ.get('REPOLENS_CHROMA_PATH', '.repolens_chroma')
# Indexing has a separate bounded source budget from report generation.
# Quick prioritizes the most relevant source so a first-time RAG build does not
# consume the much larger full-index embedding budget. Coverage is intentionally
# narrower: choose full for deep analysis or balanced for an intermediate scope.
RAG_INDEX_PROFILE = os.getenv('REPOLENS_RAG_INDEX_PROFILE', 'quick').strip().lower()
_RAG_INDEX_LIMITS = {
    'quick': (24, 35_000, 90_000),
    'balanced': (40, 80_000, 250_000),
    'full': (60, 120_000, 600_000),
}
if RAG_INDEX_PROFILE not in _RAG_INDEX_LIMITS:
    raise ValueError('REPOLENS_RAG_INDEX_PROFILE must be quick, balanced, or full')
RAG_MAX_FILES, RAG_MAX_FILE_CHARS, RAG_CONTEXT_BUDGET = _RAG_INDEX_LIMITS[RAG_INDEX_PROFILE]
# Lower actual embedding demand for Quick without changing Balanced/Full coverage.
# Snippets are selected from across real source files, not only their beginnings.
RAG_INDEX_EFFECTIVE_BUDGET = (60_000 if RAG_INDEX_PROFILE == "quick" else RAG_CONTEXT_BUDGET)

# Provider/model identity isolates local vectors from Gemini indexes. Restart on changes.
if os.getenv('REPOLENS_MODEL_PROVIDER','gemini').lower() == 'ollama':
    EMBEDDING_MODEL='ollama:'+os.getenv('OLLAMA_EMBED_MODEL','nomic-embed-text')
