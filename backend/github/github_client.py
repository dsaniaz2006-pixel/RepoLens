"""GitHub REST API client for RepoLens. No AI logic lives in this module."""

from __future__ import annotations

import base64
import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlparse

import requests
from backend.core.operation_progress import report_progress

from backend.core.config import (
    FALLBACK_SOURCE_DIRS,
    GITHUB_API_BASE,
    GITHUB_CONTENTS_MAX_BYTES,
    MAX_FILE_CHARS,
    MAX_FILES,
    MAX_FALLBACK_TREE_ENTRIES,
    REQUEST_TIMEOUT,
    TOTAL_CONTEXT_BUDGET,
)


class GitHubError(Exception):
    """Raised when a GitHub API call cannot be completed."""


class RepoNotFoundError(GitHubError):
    """Raised when GitHub returns 404 for a repository or selected file."""


class RateLimitError(GitHubError):
    """Raised when GitHub's API rate limit is exhausted."""

    def __init__(self, message: str, reset_at: datetime | None = None) -> None:
        super().__init__(message)
        self.reset_at = reset_at


class UnsupportedContentError(GitHubError):
    """Raised when a path cannot safely be used as text context."""


def parse_github_url(url: str) -> tuple[str, str]:
    """Validate an HTTPS GitHub repository URL and return ``(owner, repo)``.

    Accepts one optional trailing slash and a trailing ``.git``. It rejects
    extra path segments, query strings, fragments, credentials and non-HTTPS
    URLs so a browser URL for an issue/branch cannot be mistaken for a repo.
    """
    if url is None or not str(url).strip():
        raise ValueError(
            "A GitHub repository URL is required. Example: "
            "https://github.com/pallets/flask"
        )

    raw = str(url).strip()
    parsed = urlparse(raw)
    if parsed.scheme.lower() != "https":
        raise ValueError("Use an HTTPS repository URL starting with https://github.com/.")
    if parsed.netloc.lower() != "github.com":
        raise ValueError("Only https://github.com/ repository URLs are supported.")
    if parsed.query or parsed.fragment:
        raise ValueError("Query strings and fragments are not allowed in repository URLs.")

    parts = parsed.path.strip("/").split("/") if parsed.path.strip("/") else []
    if len(parts) != 2 or not all(parts):
        raise ValueError(
            "URL must contain an owner and a repository name, and no extra path segments, "
            "for example https://github.com/pallets/flask."
        )

    owner, repo = parts
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo or owner in {".", ".."} or repo in {".", ".."}:
        raise ValueError("Could not read a valid owner and repository from the URL.")
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", owner):
        raise ValueError("The GitHub owner name contains invalid characters.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", repo) or repo in {".", ".."}:
        raise ValueError("The GitHub repository name contains invalid characters.")
    return owner, repo


def _auth_headers() -> dict[str, str]:
    """Use an optional GitHub token without printing or logging it."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "RepoLens",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _rate_limit_reset(response: requests.Response) -> datetime | None:
    reset = response.headers.get("X-RateLimit-Reset")
    if not reset:
        return None
    try:
        return datetime.fromtimestamp(int(reset), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _raise_for_github_status(
    response: requests.Response,
    context: str,
    not_found_message: str = "Repository not found.",
) -> None:
    remaining = response.headers.get("X-RateLimit-Remaining")
    response_message = (getattr(response, "text", "") or "").lower()
    is_rate_limited = (
        response.status_code == 429
        or (response.status_code == 403 and remaining == "0")
        or (response.status_code == 403 and "rate limit" in response_message)
    )
    if is_rate_limited:
        reset_at = _rate_limit_reset(response)
        when = (
            reset_at.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
            if reset_at
            else "the retry time suggested by GitHub, or the next hour"
        )
        raise RateLimitError(
            f"GitHub rate limit reached while {context}. Try again after {when}. "
            "Set GITHUB_TOKEN in your environment to increase the public API limit.",
            reset_at=reset_at,
        )

    if response.status_code == 404:
        raise RepoNotFoundError(not_found_message)
    if response.status_code == 403:
        raise GitHubError(
            f"GitHub refused the request while {context} (HTTP 403). "
            "Check repository access and the API response headers."
        )

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise GitHubError(
            f"GitHub request failed while {context} (HTTP {response.status_code})."
        ) from exc


def _get(
    path: str,
    context: str,
    params: dict[str, Any] | None = None,
    not_found_message: str = "Repository not found.",
) -> Any:
    report_progress(None)
    url = f"{GITHUB_API_BASE}{path}"
    try:
        response = requests.get(
            url,
            headers=_auth_headers(),
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.Timeout as exc:
        raise GitHubError(f"Timed out after {REQUEST_TIMEOUT}s while {context}.") from exc
    except requests.RequestException as exc:
        # Avoid reflecting request internals that might include sensitive details.
        raise GitHubError(f"Network error while {context}: {type(exc).__name__}.") from exc

    _raise_for_github_status(response, context, not_found_message=not_found_message)
    try:
        return response.json()
    except ValueError as exc:
        raise GitHubError(f"GitHub returned a non-JSON response while {context}.") from exc


def fetch_repo_metadata(owner: str, repo: str) -> dict[str, Any]:
    """GET ``/repos/{owner}/{repo}`` and return stable, useful metadata."""
    data = _get(
        f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}",
        f"fetching metadata for {owner}/{repo}",
    )
    return {
        "private": bool(data.get("private", False)),
        "name": data.get("name") or repo,
        "full_name": data.get("full_name") or f"{owner}/{repo}",
        "description": data.get("description") or "",
        "default_branch": data.get("default_branch") or "main",
        "language": data.get("language") or "",
        "html_url": data.get("html_url") or f"https://github.com/{owner}/{repo}",
    }


def _normalize_tree_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    path = entry.get("path")
    if not path or not isinstance(path, str):
        return None
    entry_type = entry.get("type")
    if entry_type in ("file", "blob"):
        normalized_type = "blob"
    elif entry_type in ("dir", "tree"):
        normalized_type = "tree"
    else:
        return None
    return {"path": path, "type": normalized_type, "size": entry.get("size") or 0}


def fetch_tree(owner: str, repo: str, branch: str) -> tuple[list[dict[str, Any]], bool]:
    """Fetch recursive tree; use a documented bounded fallback if truncated."""
    safe_owner, safe_repo = quote(owner, safe=""), quote(repo, safe="")
    safe_branch = quote(branch, safe="")
    data = _get(
        f"/repos/{safe_owner}/{safe_repo}/git/trees/{safe_branch}",
        f"fetching tree for {owner}/{repo}@{branch}",
        params={"recursive": "1"},
    )
    if not isinstance(data, dict):
        raise GitHubError("GitHub returned an unexpected tree response.")

    truncated = bool(data.get("truncated"))
    if truncated:
        entries = fetch_tree_fallback(owner, repo, branch)
        return entries, True

    entries: list[dict[str, Any]] = []
    for raw in data.get("tree") or []:
        normalized = _normalize_tree_entry(raw)
        if normalized:
            entries.append(normalized)
    return entries, False


def fetch_tree_fallback(owner: str, repo: str, branch: str) -> list[dict[str, Any]]:
    """Bounded fallback: top-level paths plus one level in likely source dirs.

    This is intentionally a fallback, not a claim of full repository coverage.
    The caller receives ``truncated=True`` from ``fetch_tree`` so report output
    can disclose that the repository map might be incomplete.
    """
    safe_owner, safe_repo = quote(owner, safe=""), quote(repo, safe="")
    top_level = _get(
        f"/repos/{safe_owner}/{safe_repo}/contents/",
        f"fetching top-level contents for {owner}/{repo}",
        params={"ref": branch},
    )
    if not isinstance(top_level, list):
        raise GitHubError(f"Unexpected top-level contents response for {owner}/{repo}.")

    entries: list[dict[str, Any]] = []
    dirs_to_recurse: list[str] = []
    seen: set[str] = set()
    for item in top_level:
        normalized = _normalize_tree_entry(item)
        if not normalized:
            continue
        if normalized["path"] not in seen:
            entries.append(normalized)
            seen.add(normalized["path"])
        if (
            normalized["type"] == "tree"
            and normalized["path"].split("/")[-1].lower() in FALLBACK_SOURCE_DIRS
        ):
            dirs_to_recurse.append(normalized["path"])

    for directory in dirs_to_recurse:
        if len(entries) >= MAX_FALLBACK_TREE_ENTRIES:
            break
        encoded_dir = quote(directory, safe="/")
        children = _get(
            f"/repos/{safe_owner}/{safe_repo}/contents/{encoded_dir}",
            f"fetching {directory} for {owner}/{repo}",
            params={"ref": branch},
        )
        if not isinstance(children, list):
            continue
        for item in children:
            if len(entries) >= MAX_FALLBACK_TREE_ENTRIES:
                break
            normalized = _normalize_tree_entry(item)
            if normalized and normalized["path"] not in seen:
                entries.append(normalized)
                seen.add(normalized["path"])
    return entries[:MAX_FALLBACK_TREE_ENTRIES]


def truncate_text(text: str, limit: int) -> tuple[str, bool]:
    """Truncate to no more than ``limit`` characters, preferring a line end."""
    if limit <= 0:
        return "", bool(text)
    if len(text) <= limit:
        return text, False
    snippet = text[:limit]
    last_newline = snippet.rfind("\n")
    if last_newline >= limit // 2:
        snippet = snippet[: last_newline + 1]
    return snippet, True


def fetch_file_content(owner: str, repo: str, path: str, branch: str) -> str:
    """Fetch and UTF-8 decode one text file using GitHub Contents API."""
    encoded_path = quote(path, safe="/")
    data = _get(
        f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/contents/{encoded_path}",
        f"fetching file {path} from {owner}/{repo}",
        params={"ref": branch},
        not_found_message=f"File not found: {path}",
    )
    if isinstance(data, list):
        raise UnsupportedContentError(f"{path} is a directory, not a file.")
    if not isinstance(data, dict):
        raise UnsupportedContentError(f"{path} returned an unexpected content response.")

    encoding = (data.get("encoding") or "").lower()
    raw_content = data.get("content")
    if encoding != "base64" or not raw_content:
        raise UnsupportedContentError(
            f"{path} has no usable text body (encoding={encoding or 'unknown'}). "
            "GitHub may omit bodies for files over 1 MB."
        )
    try:
        raw_bytes = base64.b64decode(raw_content, validate=False)
    except (ValueError, TypeError) as exc:
        raise UnsupportedContentError(f"{path} could not be Base64-decoded.") from exc
    if b"\x00" in raw_bytes:
        raise UnsupportedContentError(f"{path} looks like a binary file.")
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UnsupportedContentError(f"{path} is not valid UTF-8 text.") from exc


def _size_lookup(tree: list[dict[str, Any]]) -> dict[str, int]:
    return {
        entry["path"]: int(entry.get("size") or 0)
        for entry in tree
        if entry.get("path") and entry.get("type") in ("blob", "file")
    }


def _looks_like_secret_content(text: str) -> bool:
    """Detect common credentials before any file text is sent to Gemini.

    This is a conservative heuristic, not a complete secret scanner. It is
    designed to catch unmistakable private-key blocks and common token formats
    without logging the matching text.
    """
    patterns = (
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
        r"\bgh[pousr]_[A-Za-z0-9]{20,}\b",
        r"\bAKIA[0-9A-Z]{16}\b",
        r"\bAIza[0-9A-Za-z_-]{30,}\b",
        r"\bsk-[A-Za-z0-9_-]{20,}\b",
        r"\bsk_(?:live|test)_[A-Za-z0-9]{16,}\b",
        r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b",
        r"\beyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _result(
    path: str,
    *,
    content: str = "",
    original_size: int | None = None,
    original_char_count: int | None = None,
    truncated: bool = False,
    skipped: bool = False,
    skip_reason: str | None = None,
) -> dict[str, Any]:
    included = len(content)
    return {
        "path": path,
        "content": content,
        # original_size is the GitHub tree size in BYTES, not characters.
        "original_size": original_size,
        "original_char_count": original_char_count,
        "char_count": included,
        "included_char_count": included,
        "truncated": truncated,
        "skipped": skipped,
        "skip_reason": skip_reason,
    }


def collect_selected_file_contents(
    owner: str,
    repo: str,
    branch: str,
    selected: list[tuple[str, int]],
    tree: list[dict[str, Any]],
    *, max_files: int | None = None, max_file_chars: int | None = None,
    total_budget: int | None = None,
    fetch_workers: int = 1, index_excerpts: bool = False,
) -> list[dict[str, Any]]:
    """Fetch only approved, unique paths under file-count and character caps.

    The selector is not blindly trusted: excluded paths and directories are
    checked again here. Every result includes byte and character metadata so
    the amount of included context can be audited.
    """
    # Import locally to avoid coupling pure ranking rules to API setup at import.
    from backend.services.file_selector import should_skip, _SOURCE_EXTS, _suffix, _is_secondary, _is_test_path
    from backend.core.config import MIN_SOURCE_CONTEXT_CHARS

    def is_implementation(path):
        return _suffix(path) in _SOURCE_EXTS and not _is_secondary(path) and not _is_test_path(path)

    sizes = _size_lookup(tree)
    tree_file_paths = set(sizes)
    file_cap = MAX_FILES if max_files is None else max_files
    char_cap = MAX_FILE_CHARS if max_file_chars is None else max_file_chars
    remaining = TOTAL_CONTEXT_BUDGET if total_budget is None else total_budget
    if min(file_cap, char_cap, remaining) < 1:
        raise ValueError('Collection limits must be positive')
    prefetched = {}
    if fetch_workers > 1:
        from concurrent.futures import ThreadPoolExecutor
        from contextvars import copy_context
        approved = list(dict.fromkeys(path for path,_ in selected[:file_cap]
            if path in tree_file_paths and not should_skip(path)
            and sizes[path] <= GITHUB_CONTENTS_MAX_BYTES))
        with ThreadPoolExecutor(max_workers=min(fetch_workers,4)) as pool:
            pending={path:pool.submit(copy_context().run,fetch_file_content,owner,repo,path,branch) for path in approved}
            for done, (path,future) in enumerate(pending.items(), 1):
                report_progress(f'Downloading source files {done}/{len(pending)}…')
                try: prefetched[path]=future.result()
                except GitHubError as exc: prefetched[path]=exc
    has_source = any(is_implementation(path) and path in tree_file_paths and not should_skip(path)
                     for path, _ in selected)
    source_remaining = min(MIN_SOURCE_CONTEXT_CHARS, remaining // 2) if has_source else 0
    results: list[dict[str, Any]] = []
    stop_reason: str | None = None
    seen: set[str] = set()

    for path, _score in selected:
        if path in seen:
            continue
        seen.add(path)
        original_size = sizes.get(path)

        if len(results) >= file_cap:
            results.append(_result(path, original_size=original_size, skipped=True,
                                   skip_reason=f"maximum file count ({file_cap}) reached"))
            continue
        if path not in tree_file_paths:
            results.append(_result(path, skipped=True, skip_reason="path is not a file in the supplied GitHub tree"))
            continue
        if should_skip(path):
            results.append(_result(path, original_size=original_size, skipped=True,
                                   skip_reason="excluded by the file safety filter"))
            continue
        if stop_reason:
            results.append(_result(path, original_size=original_size, skipped=True, skip_reason=stop_reason))
            continue
        if remaining <= 0:
            results.append(_result(path, original_size=original_size, skipped=True,
                                   skip_reason="total character budget reached"))
            continue
        if original_size is not None and original_size > GITHUB_CONTENTS_MAX_BYTES:
            results.append(_result(
                path, original_size=original_size, skipped=True,
                skip_reason=(f"file is {original_size} bytes; GitHub Contents API omits "
                             f"file bodies over {GITHUB_CONTENTS_MAX_BYTES} bytes"),
            ))
            continue

        try:
            text = prefetched[path] if path in prefetched else fetch_file_content(owner, repo, path, branch)
            if isinstance(text,Exception):
                raise text
        except RateLimitError as exc:
            stop_reason = f"GitHub rate limit reached: {exc}"
            results.append(_result(path, original_size=original_size, skipped=True, skip_reason=stop_reason))
            continue
        except (RepoNotFoundError, UnsupportedContentError, GitHubError) as exc:
            results.append(_result(path, original_size=original_size, skipped=True, skip_reason=str(exc)))
            continue

        original_char_count = len(text)
        if _looks_like_secret_content(text):
            results.append(_result(
                path,
                original_size=original_size,
                original_char_count=original_char_count,
                skipped=True,
                skip_reason="content resembles a private key or common credential token; text was not sent to Gemini",
            ))
            continue
        available = remaining if is_implementation(path) else max(0, remaining - source_remaining)
        limit = min(char_cap, available)
        if index_excerpts:
            # Give the next selected files a chance and reduce embedding volume.
            # Declarations deep inside large source files are preserved with
            # original line numbers via separate excerpt segments.
            limit = min(limit, 5_000 if is_implementation(path) else 1_600)
        if limit == 0:
            results.append(_result(path, original_size=original_size, skipped=True,
                                   skip_reason="remaining context reserved for implementation source"))
            continue
        segments = None
        if index_excerpts and is_implementation(path):
            from backend.rag.index_excerpts import source_excerpts
            segments = source_excerpts(text, path, limit=limit)
            if not segments:
                # Very long minified single-line source: retain a valid
                # line-1 prefix rather than silently dropping the file.
                prefix, _ = truncate_text(text, limit)
                segments = [{'start_line': 1, 'text': prefix}] if prefix else []
            snippet = ''.join(segment['text'] for segment in segments)
            truncated = len(snippet) < len(text)
        else:
            snippet, truncated = truncate_text(text, limit)
        remaining -= len(snippet)
        if is_implementation(path):
            source_remaining = max(0, source_remaining - len(snippet))
        included = _result(
            path,
            content=snippet,
            original_size=original_size,
            original_char_count=original_char_count,
            truncated=truncated,
        )
        if segments is not None and segments:
            included['segments'] = segments
        results.append(included)

    return results


def fetch_commit_sha(owner: str, repo: str, branch: str) -> str:
    """Pin RAG indexes to the current immutable branch-tip commit."""
    data = _get(f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/commits/{quote(branch, safe='')}",
                f"fetching revision for {owner}/{repo}")
    sha = data.get('sha') if isinstance(data, dict) else None
    if not isinstance(sha, str) or len(sha) != 40 or any(c not in '0123456789abcdefABCDEF' for c in sha):
        raise GitHubError('GitHub did not return a valid commit SHA')
    return sha
