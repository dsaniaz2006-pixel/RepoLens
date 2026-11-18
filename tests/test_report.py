from pathlib import Path

import pytest

from backend.services.report import ReportError, render_report, save_report
from tests.test_analyzer import TREE, valid_analysis

METADATA = {
    "name": "sample", "full_name": "owner/sample", "description": "A demo project",
    "default_branch": "main", "language": "Python", "html_url": "https://github.com/owner/sample",
}


def test_markdown_contains_all_required_sections():
    report = render_report(valid_analysis(), METADATA, TREE)
    for heading in [
        "## 1. Project summary", "## 2. Technology stack and evidence",
        "## 3. Repository and folder map", "## 4. Likely entry points and important files",
        "## 5. Recommended reading path", "## 6. Representative code/request flow",
        "## 7. Evidence-based improvement idea", "## 8. Limitations and uncertain findings",
    ]:
        assert heading in report


def test_nonexistent_paths_are_filtered_from_report():
    analysis = valid_analysis()
    analysis["entry_points"].append({"path": "fake.py", "reason": "fake", "evidence_paths": ["fake.py"]})
    analysis["reading_path"].append({"path": "not/real.py", "reason": "fake"})
    analysis["improvement_idea"]["evidence_paths"] = ["nonexistent.py"]
    report = render_report(analysis, METADATA, TREE)
    assert "fake.py" not in report
    assert "not/real.py" not in report
    assert "nonexistent.py" not in report


def test_supported_flow_renders_steps():
    report = render_report(valid_analysis(), METADATA, TREE)
    assert "The entry point delegates to a service." in report
    assert "src/service.py" in report


def test_unsupported_flow_is_labelled_not_invented():
    analysis = valid_analysis()
    analysis["code_flow"] = {"supported": False, "summary": "Insufficient evidence.", "steps": []}
    report = render_report(analysis, METADATA, TREE)
    assert "flow is omitted" in report


def test_truncated_tree_is_disclosed():
    report = render_report(valid_analysis(), METADATA, TREE, tree_truncated=True)
    assert "truncated recursive tree" in report
    assert "Incomplete (truncated fallback used)" in report


def test_saves_predictable_file_and_creates_directory(tmp_path):
    output_dir = tmp_path / "reports"
    saved = save_report(valid_analysis(), METADATA, TREE, "owner", "sample", output_dir=output_dir)
    assert saved == output_dir / "owner-sample-report.md"
    assert saved.exists()
    assert "RepoLens Onboarding Report" in saved.read_text(encoding="utf-8")


def test_existing_report_is_not_silently_overwritten(tmp_path):
    output_dir = tmp_path / "reports"
    output_dir.mkdir()
    target = output_dir / "owner-sample-report.md"
    target.write_text("keep me", encoding="utf-8")
    with pytest.raises(ReportError, match="will not overwrite"):
        save_report(valid_analysis(), METADATA, TREE, "owner", "sample", output_dir=output_dir)
    assert target.read_text(encoding="utf-8") == "keep me"


def test_explicit_overwrite_replaces_report(tmp_path):
    output_dir = tmp_path / "reports"
    output_dir.mkdir()
    target = output_dir / "owner-sample-report.md"
    target.write_text("old report", encoding="utf-8")
    save_report(valid_analysis(), METADATA, TREE, "owner", "sample", output_dir=output_dir, overwrite=True)
    assert "old report" not in target.read_text(encoding="utf-8")
