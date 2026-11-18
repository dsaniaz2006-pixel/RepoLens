"""Filter and rank repository files. Pure logic — no GitHub or AI calls."""

from __future__ import annotations

from pathlib import PurePosixPath

from backend.core.config import MAX_FILES, SKIP_DIR_NAMES, SKIP_EXTENSIONS, SKIP_FILE_NAMES

_SKIP_DIRS = {name.lower() for name in SKIP_DIR_NAMES}
_SKIP_FILES = {name.lower() for name in SKIP_FILE_NAMES}
_SKIP_EXTS = {ext.lower() for ext in SKIP_EXTENSIONS}

_README_NAMES = {"readme", "readme.md", "readme.rst", "readme.txt"}
_ROOT_PROJECT_DOCS = {
    "contributing.md",
    "contributing.rst",
    "changelog.md",
    "changelog.rst",
    "changes.md",
    "changes.rst",
    "license",
    "license.md",
    "license.txt",
    "code_of_conduct.md",
    "security.md",
    "authors",
    "authors.md",
}
_CONFIG_NAMES = {
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "package.json",
    "cargo.toml",
    "go.mod",
    "gemfile",
    "composer.json",
    "pom.xml",
    "build.gradle",
    "makefile",
    "cmakelists.txt",
    "tsconfig.json",
    "requirements.txt",
    "pipfile",
    "environment.yml",
    "dockerfile",
}
_ENTRY_NAMES = {
    "main.py",
    "app.py",
    "index.js",
    "index.ts",
    "index.jsx",
    "index.tsx",
    "server.py",
    "server.js",
    "wsgi.py",
    "asgi.py",
    "__main__.py",
    "manage.py",
    "main.go",
    "main.rs",
    "lib.rs",
    "mod.rs",
}
_SOURCE_EXTS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".rb",
    ".php",
    ".cs",
    ".kt",
    ".c",
    ".h",
    ".cpp",
    ".vue",
    ".svelte",
}
_DOC_EXTS = {".md", ".rst", ".txt", ".adoc"}
_HIGH_DIR_PARTS = {
    "src",
    "lib",
    "app",
    "pkg",
    "packages",
    "routes",
    "models",
    "controllers",
    "views",
    "api",
    "core",
    "backend",
    "frontend",
    "server",
    "client",
}
_TEST_DIR_PARTS = {"test", "tests", "__tests__", "spec", "specs"}
_DOC_DIR_PARTS = {"docs", "doc", "documentation"}
_EXAMPLE_DIR_PARTS = {
    "examples",
    "example",
    "samples",
    "sample",
    "demo",
    "demos",
    "benchmarks",
    "benchmark",
}
_SECONDARY_DIR_PARTS = _DOC_DIR_PARTS | _EXAMPLE_DIR_PARTS


def _parts(path: str) -> tuple[str, ...]:
    return PurePosixPath(path.replace("\\", "/")).parts


def _filename(path: str) -> str:
    return PurePosixPath(path.replace("\\", "/")).name


def _suffix(path: str) -> str:
    return PurePosixPath(path.replace("\\", "/")).suffix.lower()


def _dir_parts(path: str) -> set[str]:
    return {part.lower() for part in _parts(path)[:-1]}


def _is_secondary(path: str) -> bool:
    """True for docs, examples, demos, and similar supporting trees."""
    return bool(_dir_parts(path) & _SECONDARY_DIR_PARTS)


def _is_core_tree(path: str) -> bool:
    return bool(_dir_parts(path) & _HIGH_DIR_PARTS)


def _is_test_path(path: str) -> bool:
    parts = _parts(path)
    name = _filename(path).lower()
    if any(part.lower() in _TEST_DIR_PARTS for part in parts):
        return True
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    if ".test." in name or ".spec." in name:
        return True
    return False


def should_skip(path: str) -> bool:
    """Return True if this path should never be selected.

    Skip-directory names match any segment of the path (for example
    src/node_modules/pkg/index.js), not only a prefix.
    Tests directories are not skipped — they just score lower later.
    """
    if not path or not str(path).strip():
        return True

    parts = _parts(path)
    if any(part.lower() in _SKIP_DIRS for part in parts):
        return True

    name = _filename(path).lower()
    if name in _SKIP_FILES:
        return True
    # Template/example env files contain variable names rather than real
    # secrets and are useful context. Actual environment variants are skipped.
    safe_env_templates = (".env.example", ".env.sample", ".env.template")
    if name == ".env" or (name.startswith(".env.") and name not in safe_env_templates):
        return True
    if name.startswith("id_rsa") or name.startswith("id_ed25519"):
        return True
    if _suffix(path) not in _SOURCE_EXTS and ("credential" in name or "secret" in name or "token" == name.split(".")[0]):
        return True
    if name.startswith(("service-account", "service_account", "private-key", "private_key")):
        return True
    if _suffix(path) in _SKIP_EXTS:
        return True

    return False


def score_path(path: str) -> int:
    """Return a numeric priority. Higher means more useful for analysis.

    Location matters as much as filename: a root README or pyproject.toml
    outranks the same filename under examples/ or docs/. Core source under
    src/ (and similar) outranks documentation build files.
    """
    if should_skip(path):
        return 0

    name = _filename(path).lower()
    suffix = _suffix(path)
    parts = _parts(path)
    depth = max(len(parts) - 1, 0)
    secondary = _is_secondary(path)
    core = _is_core_tree(path) and not secondary

    if name in _README_NAMES:
        if depth == 0:
            return 1000
        if secondary:
            return max(140 - depth, 50)
        return max(380 - depth, 120)

    if depth == 0 and name in _ROOT_PROJECT_DOCS:
        return 250

    if name in _CONFIG_NAMES:
        if depth == 0:
            return 900
        if secondary:
            return 60
        if core:
            return 520
        return 180

    if _is_test_path(path):
        if secondary:
            return max(90 - depth, 40)
        return max(240 - depth, 80)

    if name in _ENTRY_NAMES:
        if secondary:
            return max(180 - depth, 60)
        if depth == 0:
            return 820
        if core:
            return 760 - depth
        return 640 - depth

    if _dir_parts(path) & _DOC_DIR_PARTS:
        return max(70 - depth, 20)

    if suffix in _DOC_EXTS and name not in _README_NAMES:
        if depth == 0:
            return 250
        return max(70 - depth, 20)

    if suffix in _SOURCE_EXTS:
        if secondary:
            return max(150 - depth, 50)
        if core:
            return 680 - depth
        return 420 - depth

    if secondary:
        return 40
    return max(50 - depth, 10)


def filter_and_rank(
    tree: list[dict],
    limit: int | None = None,
) -> list[tuple[str, int]]:
    """Filter skipped paths, score files, and return the top N (path, score) pairs.

    Directories are never selected. N comes from config.MAX_FILES unless
    a caller passes limit (useful in tests).
    """
    cap = MAX_FILES if limit is None else limit
    scored: list[tuple[str, int]] = []

    for entry in tree:
        if entry.get("type") not in ("blob", "file"):
            continue
        path = entry.get("path")
        if not path or should_skip(path):
            continue
        score = score_path(path)
        if score <= 0:
            continue
        scored.append((path, score))

    scored.sort(key=lambda item: (-item[1], item[0]))
    return scored[:cap]


def _selection_reason(path: str) -> str:
    """Explain the heuristic that gives a file useful analysis context."""
    name = _filename(path).lower()
    parts = _parts(path)
    depth = max(len(parts) - 1, 0)
    directories = {part.lower() for part in parts[:-1]}
    if name in _README_NAMES:
        return "README explains project purpose and setup" if depth == 0 else "nested README provides localized context"
    if name in _CONFIG_NAMES:
        return "project manifest/configuration reveals dependencies and tooling"
    if name in _ENTRY_NAMES:
        return "likely application or package entry point"
    if _is_test_path(path):
        return "test file can reveal expected behavior and important interfaces"
    if directories & {"routes", "controllers", "services", "models", "api"}:
        return "application component in a route/controller/service/model area"
    if _suffix(path) in _SOURCE_EXTS:
        return "source file likely contains implementation details"
    if _suffix(path) in _DOC_EXTS:
        return "documentation provides supporting project context"
    return "supporting file selected by general path heuristic"


def _skip_reason(path: str, selected_paths: set[str], score: int) -> str:
    """Explain why a file was selected or not selected."""
    if not path or not str(path).strip():
        return "empty path"
    parts = _parts(path)
    for part in parts:
        if part.lower() in _SKIP_DIRS:
            return f"inside excluded directory '{part}'"
    name = _filename(path).lower()
    if should_skip(path):
        if name.startswith(".env"):
            return "environment file may contain secrets"
        if ("credential" in name or "secret" in name or name.startswith(("id_rsa", "id_ed25519", "service-account", "service_account", "private-key", "private_key"))):
            return "credential or secret-like filename"
        if _suffix(path) in _SKIP_EXTS:
            return f"excluded binary, generated, lock, or key-file extension '{_suffix(path)}'"
        return "excluded by filename safety rule"
    if score <= 0:
        return "path has no positive selection score"
    if path in selected_paths:
        return _selection_reason(path)
    return "eligible file ranked below the MAX_FILES selection limit"


def selection_audit(tree: list[dict], selected: list[tuple[str, int]]) -> list[dict[str, object]]:
    """Return an auditable decision for each unique file path in the tree.

    This is deliberately separate from ``filter_and_rank`` so the original
    ``(path, score)`` return shape remains compatible with the existing CLI
    and its tests.
    """
    selected_scores = {path: score for path, score in selected}
    audit: list[dict[str, object]] = []
    seen: set[str] = set()
    for entry in tree:
        path = entry.get("path")
        if not isinstance(path, str) or not path or path in seen:
            continue
        seen.add(path)
        is_file = entry.get("type") in ("blob", "file")
        score = selected_scores.get(path, score_path(path) if is_file else 0)
        decision = "selected" if path in selected_scores else "skipped"
        if not is_file:
            reason = "directory entries are not selected as file contents"
        else:
            reason = _skip_reason(path, set(selected_scores), score)
        audit.append({"path": path, "decision": decision, "score": score, "reason": reason})
    return audit


def rank_for_rag_index(tree: list[dict], limit: int) -> list[tuple[str, int]]:
    """Prioritize representative implementation paths for a *bounded* RAG index.

    The regular report uses the historical ranking unchanged. For Quick RAG,
    route / request / handler code is more useful than similarly-scored
    alphabetical source files. Paths must still pass the original safety filter.
    """
    candidates = filter_and_rank(tree, limit=max(limit * 8, limit))
    def bonus(path):
        name = _filename(path).lower().replace('-', '_')
        if _suffix(path) not in _SOURCE_EXTS or _is_test_path(path) or _is_secondary(path):
            return 0
        for keyword, points in (
            ('routes', 280), ('router', 280), ('routing', 270),
            ('scaffold', 255), ('dispatch', 250), ('middleware', 240),
            ('request', 210), ('views', 200), ('controller', 190),
            ('handler', 190), ('session', 180), ('auth', 180),
            ('api', 160), ('app', 130), ('server', 120), ('main', 110),
        ):
            if keyword in name:
                return points
        return 0
    return sorted(candidates, key=lambda item: (-item[1]-bonus(item[0]), item[0]))[:limit]
