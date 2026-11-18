"""Unit tests for GitHub API behavior. All HTTP responses are mocked."""

import base64
from unittest.mock import MagicMock

import pytest
import requests

import backend.github.github_client as github_client
from backend.github.github_client import (
    GitHubError,
    RateLimitError,
    RepoNotFoundError,
    UnsupportedContentError,
    collect_selected_file_contents,
    fetch_file_content,
    fetch_repo_metadata,
    fetch_tree,
    parse_github_url,
)


def response(status=200, payload=None, headers=None, text=""):
    obj = MagicMock()
    obj.status_code = status
    obj.headers = headers or {}
    obj.text = text
    obj.json.return_value = payload
    if status >= 400:
        obj.raise_for_status.side_effect = requests.HTTPError(f"HTTP {status}")
    else:
        obj.raise_for_status.return_value = None
    return obj


def test_metadata_and_default_branch(monkeypatch):
    monkeypatch.setattr(github_client.requests, "get", lambda *a, **k: response(200, {
        "name": "sample", "full_name": "owner/sample", "description": "A repo",
        "default_branch": "develop", "language": "Python", "html_url": "https://github.com/owner/sample",
    }))
    data = fetch_repo_metadata("owner", "sample")
    assert data["default_branch"] == "develop"
    assert data["full_name"] == "owner/sample"
    assert data["language"] == "Python"


def test_successful_recursive_tree(monkeypatch):
    monkeypatch.setattr(github_client.requests, "get", lambda *a, **k: response(200, {
        "truncated": False,
        "tree": [
            {"path": "README.md", "type": "blob", "size": 20},
            {"path": "src", "type": "tree"},
            {"path": "ignored", "type": "commit"},
        ],
    }))
    entries, truncated = fetch_tree("owner", "sample", "main")
    assert truncated is False
    assert entries == [
        {"path": "README.md", "type": "blob", "size": 20},
        {"path": "src", "type": "tree", "size": 0},
    ]


def test_truncated_tree_uses_fallback(monkeypatch):
    monkeypatch.setattr(github_client.requests, "get", lambda *a, **k: response(200, {"truncated": True, "tree": []}))
    monkeypatch.setattr(github_client, "fetch_tree_fallback", lambda *a: [{"path": "README.md", "type": "blob", "size": 5}])
    entries, truncated = fetch_tree("owner", "sample", "main")
    assert truncated is True
    assert entries[0]["path"] == "README.md"


def test_repo_not_found(monkeypatch):
    monkeypatch.setattr(github_client.requests, "get", lambda *a, **k: response(404, {}, text="secret response body"))
    with pytest.raises(RepoNotFoundError):
        fetch_repo_metadata("owner", "missing")


def test_rate_limit_has_reset_message(monkeypatch):
    monkeypatch.setattr(github_client.requests, "get", lambda *a, **k: response(
        403, {}, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "2000000000"}
    ))
    with pytest.raises(RateLimitError, match="rate limit"):
        fetch_repo_metadata("owner", "sample")


def test_server_error_is_reported_without_response_body(monkeypatch):
    monkeypatch.setattr(github_client.requests, "get", lambda *a, **k: response(500, {}, text="sensitive body"))
    with pytest.raises(GitHubError, match="HTTP 500") as exc:
        fetch_repo_metadata("owner", "sample")
    assert "sensitive body" not in str(exc.value)


def test_timeout_is_reported(monkeypatch):
    def timeout(*args, **kwargs):
        raise requests.Timeout("secret-token-not-for-output")
    monkeypatch.setattr(github_client.requests, "get", timeout)
    with pytest.raises(GitHubError, match="Timed out") as exc:
        fetch_repo_metadata("owner", "sample")
    assert "secret-token" not in str(exc.value)


def test_fetch_file_content_base64_decodes_utf8(monkeypatch):
    payload = {"encoding": "base64", "content": base64.b64encode("hello λ".encode()).decode()}
    monkeypatch.setattr(github_client.requests, "get", lambda *a, **k: response(200, payload))
    assert fetch_file_content("owner", "sample", "src/hello.py", "main") == "hello λ"


def test_fetch_file_content_rejects_binary(monkeypatch):
    payload = {"encoding": "base64", "content": base64.b64encode(b"\x00\x01\x02").decode()}
    monkeypatch.setattr(github_client.requests, "get", lambda *a, **k: response(200, payload))
    with pytest.raises(UnsupportedContentError, match="binary"):
        fetch_file_content("owner", "sample", "image.bin", "main")


def test_selected_file_per_file_truncation(monkeypatch):
    monkeypatch.setattr(github_client, "MAX_FILE_CHARS", 8)
    monkeypatch.setattr(github_client, "TOTAL_CONTEXT_BUDGET", 100)
    monkeypatch.setattr(github_client, "fetch_file_content", lambda *args: "abcdefghijklmnopqrst")
    results = collect_selected_file_contents(
        "owner", "sample", "main", [("src/a.py", 500)],
        [{"path": "src/a.py", "type": "blob", "size": 20}],
    )
    assert results[0]["content"] == "abcdefgh"
    assert results[0]["truncated"] is True
    assert results[0]["original_char_count"] == 20
    assert results[0]["included_char_count"] == 8


def test_total_budget_is_never_exceeded(monkeypatch):
    monkeypatch.setattr(github_client, "MAX_FILE_CHARS", 6)
    monkeypatch.setattr(github_client, "TOTAL_CONTEXT_BUDGET", 10)
    monkeypatch.setattr(github_client, "fetch_file_content", lambda owner, repo, path, branch: {
        "a.py": "abcdefghij", "b.py": "klmnopqrst", "c.py": "uvwxyz",
    }[path])
    selected = [("a.py", 100), ("b.py", 90), ("c.py", 80)]
    tree = [{"path": path, "type": "blob", "size": 10} for path, _ in selected]
    results = collect_selected_file_contents("owner", "sample", "main", selected, tree)
    assert sum(item["included_char_count"] for item in results) <= 10
    assert results[0]["included_char_count"] == 6
    assert results[1]["included_char_count"] == 4
    assert results[2]["skipped"] is True


def test_collector_skips_secret_and_unapproved_paths(monkeypatch):
    def should_never_fetch(*args):
        raise AssertionError("excluded path must not be fetched")
    monkeypatch.setattr(github_client, "fetch_file_content", should_never_fetch)
    selected = [(".env.production", 100), ("secrets.json", 90), ("ghost.py", 80)]
    tree = [
        {"path": ".env.production", "type": "blob", "size": 1},
        {"path": "secrets.json", "type": "blob", "size": 1},
    ]
    results = collect_selected_file_contents("owner", "sample", "main", selected, tree)
    assert all(item["skipped"] for item in results)
    assert "safety filter" in results[0]["skip_reason"]
    assert "safety filter" in results[1]["skip_reason"]
    assert "not a file" in results[2]["skip_reason"]


def test_rate_limit_stops_further_content_requests(monkeypatch):
    calls = []
    def fake_fetch(owner, repo, path, branch):
        calls.append(path)
        raise RateLimitError("rate limit reached")
    monkeypatch.setattr(github_client, "fetch_file_content", fake_fetch)
    selected = [("a.py", 3), ("b.py", 2)]
    tree = [{"path": path, "type": "blob", "size": 1} for path, _ in selected]
    results = collect_selected_file_contents("owner", "sample", "main", selected, tree)
    assert calls == ["a.py"]
    assert results[0]["skipped"] is True
    assert "rate limit" in results[1]["skip_reason"]


def test_duplicate_selected_path_is_only_processed_once(monkeypatch):
    monkeypatch.setattr(github_client, "fetch_file_content", lambda *args: "content")
    selected = [("a.py", 100), ("a.py", 90)]
    tree = [{"path": "a.py", "type": "blob", "size": 7}]
    results = collect_selected_file_contents("owner", "sample", "main", selected, tree)
    assert len(results) == 1


def test_content_matching_a_private_key_is_skipped_before_model_context(monkeypatch):
    private_key = "-----BEGIN PRIVATE KEY-----\nFAKE-MATERIAL\n-----END PRIVATE KEY-----"
    monkeypatch.setattr(github_client, "fetch_file_content", lambda *args: private_key)
    selected = [("src/config.py", 100)]
    tree = [{"path": "src/config.py", "type": "blob", "size": 100}]
    results = collect_selected_file_contents("owner", "sample", "main", selected, tree)
    assert results[0]["skipped"] is True
    assert results[0]["content"] == ""
    assert "not sent to Gemini" in results[0]["skip_reason"]


def test_content_matching_common_token_is_skipped(monkeypatch):
    fake_token = "ghp_" + "A" * 36
    monkeypatch.setattr(github_client, "fetch_file_content", lambda *args: f"TOKEN={fake_token}")
    selected = [("src/settings.py", 100)]
    tree = [{"path": "src/settings.py", "type": "blob", "size": 40}]
    results = collect_selected_file_contents("owner", "sample", "main", selected, tree)
    assert results[0]["skipped"] is True
    assert fake_token not in results[0]["skip_reason"]


def test_secondary_rate_limit_429_is_reported_even_without_remaining_header(monkeypatch):
    monkeypatch.setattr(github_client.requests, "get", lambda *a, **k: response(429, {}, text="secondary rate limit"))
    with pytest.raises(RateLimitError, match="rate limit"):
        fetch_repo_metadata("owner", "sample")
