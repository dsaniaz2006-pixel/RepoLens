import pytest

from backend.github.github_client import parse_github_url


def test_valid_https_url():
    assert parse_github_url("https://github.com/pallets/flask") == ("pallets", "flask")


def test_url_with_trailing_slash():
    assert parse_github_url("https://github.com/pallets/flask/") == ("pallets", "flask")


def test_url_with_git_suffix():
    assert parse_github_url("https://github.com/pallets/flask.git") == ("pallets", "flask")


def test_non_github_url():
    with pytest.raises(ValueError, match="github.com"):
        parse_github_url("https://gitlab.com/pallets/flask")


def test_url_missing_repo_name():
    with pytest.raises(ValueError, match="owner and a repository"):
        parse_github_url("https://github.com/pallets")


def test_empty_string():
    with pytest.raises(ValueError, match="required"):
        parse_github_url("")

@pytest.mark.parametrize(
    "url",
    [
        "ftp://github.com/pallets/flask",
        "http://github.com/pallets/flask",
        "https://github.com/pallets/flask/issues/1",
        "https://github.com/pallets/flask?tab=readme",
        "https://github.com/pallets/flask#readme",
        "https://evilgithub.com/pallets/flask",
        "https://user@github.com/pallets/flask",
    ],
)
def test_malformed_or_non_repository_urls_are_rejected(url):
    with pytest.raises(ValueError):
        parse_github_url(url)


def test_safe_env_example_is_not_classified_as_a_secret():
    # .env.example documents variable names and is safe to use as context.
    from backend.services.file_selector import should_skip
    assert should_skip(".env.example") is False


def test_invalid_owner_and_repository_characters_are_rejected():
    for url in [
        "https://github.com/owner name/repo",
        "https://github.com/owner/repo%20name",
        "https://github.com/owner/repo!",
    ]:
        with pytest.raises(ValueError):
            parse_github_url(url)
