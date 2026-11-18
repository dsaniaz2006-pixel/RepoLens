from tests.test_analyzer import TREE, valid_analysis
import backend.cli.main as repolens_main


def test_main_runs_pipeline_and_saves_report(monkeypatch, tmp_path, capsys):
    metadata = {
        "name": "sample", "full_name": "owner/sample", "description": "A demo project",
        "default_branch": "main", "language": "Python", "html_url": "https://github.com/owner/sample",
    }
    monkeypatch.setattr(repolens_main, "fetch_repo_metadata", lambda owner, repo: metadata)
    monkeypatch.setattr(repolens_main, "fetch_tree", lambda owner, repo, branch: (TREE, False))
    monkeypatch.setattr(repolens_main, "filter_and_rank", lambda tree: [("README.md", 100), ("src/main.py", 90)])
    monkeypatch.setattr(repolens_main, "collect_selected_file_contents", lambda *args: [
        {"path": "README.md", "content": "overview", "skipped": False, "included_char_count": 8},
        {"path": "src/main.py", "content": "def main(): pass", "skipped": False, "included_char_count": 16},
    ])
    monkeypatch.setattr(repolens_main, "analyze_repository", lambda *args, **kwargs: valid_analysis())

    result = repolens_main.main([
        "https://github.com/owner/sample", "--output-dir", str(tmp_path)
    ])
    assert result == 0
    saved = tmp_path / "owner-sample-report.md"
    assert saved.exists()
    assert "Project summary" in saved.read_text(encoding="utf-8")
    assert "Report saved" in capsys.readouterr().out


def test_main_rejects_invalid_url_before_network_calls(capsys):
    result = repolens_main.main(["https://github.com/owner/repo/issues/1"])
    assert result == 2
    assert "Invalid repository URL" in capsys.readouterr().err
