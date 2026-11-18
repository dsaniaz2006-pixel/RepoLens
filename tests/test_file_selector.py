from backend.core.config import MAX_FILES
from backend.services.file_selector import filter_and_rank, score_path, should_skip


def _file(path: str) -> dict:
    return {"path": path, "type": "blob", "size": 100}


def _dir(path: str) -> dict:
    return {"path": path, "type": "tree", "size": 0}


def test_readme_receives_a_high_score():
    readme = score_path("README.md")
    assert readme > score_path("src/app.py")
    assert readme > score_path("package.json")
    assert readme > score_path("tests/test_app.py")


def test_node_modules_is_excluded():
    assert should_skip("node_modules/index.js") is True
    assert should_skip("web/node_modules/lodash/index.js") is True
    assert score_path("node_modules/index.js") == 0

    selected = filter_and_rank(
        [_file("README.md"), _file("node_modules/index.js"), _file("src/app.py")]
    )
    paths = [path for path, _score in selected]
    assert "node_modules/index.js" not in paths


def test_env_files_and_lockfiles_are_excluded():
    assert should_skip(".env") is True
    assert should_skip("backend/.env.local") is True
    assert should_skip("uv.lock") is True
    assert should_skip("package-lock.json") is True
    assert should_skip("pnpm-lock.yaml") is True

    selected = filter_and_rank(
        [
            _file("README.md"),
            _file(".env"),
            _file("uv.lock"),
            _file("package-lock.json"),
            _file("src/main.py"),
        ]
    )
    paths = [path for path, _score in selected]
    assert ".env" not in paths
    assert "uv.lock" not in paths
    assert "package-lock.json" not in paths


def test_nested_tests_directory_is_not_excluded():
    nested = "examples/tutorial/tests/test_auth.py"
    assert should_skip(nested) is False
    assert score_path(nested) > 0

    selected = filter_and_rank(
        [_file("README.md"), _file(nested), _file("src/app.py")]
    )
    paths = [path for path, _score in selected]
    assert nested in paths
    assert score_path(nested) < score_path("src/app.py")


def test_important_source_files_can_be_selected():
    selected = filter_and_rank(
        [
            _file("README.md"),
            _file("src/flask/app.py"),
            _file("node_modules/left-pad/index.js"),
            _file("dist/bundle.js"),
        ]
    )
    paths = [path for path, _score in selected]
    assert "src/flask/app.py" in paths
    assert "README.md" in paths


def test_selection_limit_is_respected():
    tree = [_file(f"src/module_{index:03d}.py") for index in range(MAX_FILES + 15)]
    selected = filter_and_rank(tree)
    assert len(selected) == MAX_FILES


def test_directories_are_not_treated_as_files():
    selected = filter_and_rank(
        [
            _dir("src"),
            _dir("src/flask"),
            _file("src/flask/app.py"),
            _dir("tests"),
        ]
    )
    paths = [path for path, _score in selected]
    assert "src" not in paths
    assert "src/flask" not in paths
    assert "tests" not in paths
    assert "src/flask/app.py" in paths


def test_results_are_ranked_descending_by_score():
    selected = filter_and_rank(
        [
            _file("docs/quickstart.rst"),
            _file("README.md"),
            _file("src/flask/app.py"),
            _file("tests/test_basic.py"),
            _file("pyproject.toml"),
        ]
    )
    scores = [score for _path, score in selected]
    assert scores == sorted(scores, reverse=True)
    assert selected[0][0] == "README.md"


def test_root_readme_ranks_above_nested_example_readme():
    root = score_path("README.md")
    nested = score_path("examples/demo/README.md")
    assert root > nested
    assert root > score_path("examples/tutorial/README.rst")

    selected = filter_and_rank(
        [
            _file("examples/demo/README.md"),
            _file("src/pkg/app.py"),
            _file("README.md"),
        ]
    )
    assert selected[0][0] == "README.md"


def test_core_source_ranks_above_docs_and_example_config():
    core_entry = "src/pkg/app.py"
    core_source = "src/pkg/helpers.py"
    docs_make = "docs/Makefile"
    example_config = "examples/demo/pyproject.toml"

    assert score_path(core_entry) > score_path(docs_make)
    assert score_path(core_source) > score_path(docs_make)
    assert score_path(core_entry) > score_path(example_config)
    assert score_path(core_source) > score_path(example_config)
    assert score_path("pyproject.toml") > score_path(example_config)

    selected = filter_and_rank(
        [
            _file("README.md"),
            _file("pyproject.toml"),
            _file(core_entry),
            _file(core_source),
            _file(docs_make),
            _file(example_config),
            _file("docs/index.rst"),
            _file("examples/demo/README.md"),
        ]
    )
    paths = [path for path, _score in selected]
    assert paths.index(core_entry) < paths.index(docs_make)
    assert paths.index(core_source) < paths.index(docs_make)
    assert paths.index(core_entry) < paths.index(example_config)
    assert paths.index(core_source) < paths.index(example_config)


def test_common_credential_and_private_key_files_are_excluded():
    for path in [
        ".env.production", "secrets.json", "credentials.json", "config/id_rsa",
        "certs/server.pem", "private/signing.key", ".npmrc", ".pypirc",
    ]:
        assert should_skip(path), path


def test_env_example_is_allowed_but_real_env_is_skipped():
    assert should_skip(".env")
    assert should_skip(".env.production")
    assert not should_skip(".env.example")


def test_selection_audit_records_selected_and_skipped_reasons():
    from backend.services.file_selector import selection_audit
    tree = [
        _file("README.md"),
        _file("src/main.py"),
        _file("node_modules/pkg/index.js"),
        _dir("src"),
    ]
    selected = filter_and_rank(tree, limit=1)
    audit = selection_audit(tree, selected)
    assert any(item["path"] == "README.md" and item["decision"] == "selected" and item["reason"] for item in audit)
    assert any(item["path"] == "src/main.py" and "MAX_FILES" in item["reason"] for item in audit)
    assert any(item["path"] == "node_modules/pkg/index.js" and "excluded directory" in item["reason"] for item in audit)
