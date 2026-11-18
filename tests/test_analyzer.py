"""Gemini analysis tests use mocked responses and consume no API credits."""

import json
from types import SimpleNamespace

import pytest

from backend.ai.analyzer import AnalyzerError, analyze_repository, validate_analysis

TREE = [
    {"path": "README.md", "type": "blob"},
    {"path": "pyproject.toml", "type": "blob"},
    {"path": "src/main.py", "type": "blob"},
    {"path": "src/service.py", "type": "blob"},
    {"path": "tests/test_service.py", "type": "blob"},
    {"path": "src", "type": "tree"},
]


def valid_analysis():
    return {
        "project_summary": "A small Python application with a service layer.",
        "tech_stack": [{"name": "Python", "explanation": "The source files use Python.", "evidence_paths": ["pyproject.toml", "src/main.py"]}],
        "repository_map": [{"path": "src", "purpose": "Application source.", "evidence_paths": ["src/main.py"]}],
        "entry_points": [{"path": "src/main.py", "reason": "Likely application entry point.", "evidence_paths": ["src/main.py"]}],
        "reading_path": [
            {"path": "README.md", "reason": "Start with the project overview."},
            {"path": "pyproject.toml", "reason": "Check dependencies and configuration."},
            {"path": "src/main.py", "reason": "Follow the main execution path."},
        ],
        "code_flow": {"supported": True, "summary": "The entry point delegates to a service.", "steps": [
            {"path": "src/main.py", "role": "Entry point.", "evidence": "Calls the service function."},
            {"path": "src/service.py", "role": "Service logic.", "evidence": "Defines the called function."},
        ]},
        "improvement_idea": {"idea": "Add input validation tests.", "evidence_paths": ["src/service.py"], "assumptions": ["Inputs may come from external callers."]},
        "limitations": ["No live application execution was performed."],
    }


class FakeModels:
    def __init__(self, text=None, error=None):
        self.text = text
        self.error = error
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.text)


class FakeClient:
    def __init__(self, text=None, error=None):
        self.models = FakeModels(text, error)


def test_valid_analysis_is_accepted():
    validated = validate_analysis(valid_analysis(), [entry["path"] for entry in TREE])
    assert validated["tech_stack"][0]["name"] == "Python"
    assert len(validated["reading_path"]) == 3


def test_analyzer_calls_mocked_gemini_and_returns_validated_result(monkeypatch):
    payload = json.dumps(valid_analysis())
    client = FakeClient(text=payload)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = analyze_repository(
        {"full_name": "owner/sample"}, TREE,
        [{"path": e["path"], "content": "source evidence", "skipped": False}
         for e in TREE if e["type"] == "blob"],
        client=client,
    )
    assert result["project_summary"].startswith("A small Python")
    assert client.models.calls[0]["model"] == "gemini-3.5-flash-lite"
    assert client.models.calls[0]["config"]["response_mime_type"] == "application/json"


def test_missing_api_key_fails_with_setup_message(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(AnalyzerError, match="GEMINI_API_KEY is missing"):
        analyze_repository({}, TREE, [])


def test_api_error_does_not_leak_exception_contents():
    client = FakeClient(error=RuntimeError("API key SUPER_SECRET_KEY was rejected"))
    with pytest.raises(AnalyzerError, match="Gemini API request failed") as exc:
        analyze_repository({}, TREE, [], client=client)
    assert "SUPER_SECRET_KEY" not in str(exc.value)


def test_empty_response_is_rejected():
    with pytest.raises(AnalyzerError, match="empty response"):
        analyze_repository({}, TREE, [], client=FakeClient(text="  "))


def test_malformed_json_is_rejected():
    with pytest.raises(AnalyzerError, match="malformed JSON"):
        analyze_repository({}, TREE, [], client=FakeClient(text="{not json"))


def test_nonexistent_path_is_rejected():
    data = valid_analysis()
    data["entry_points"][0]["path"] = "src/imaginary.py"
    with pytest.raises(AnalyzerError, match="not present in the supplied GitHub tree"):
        validate_analysis(data, [entry["path"] for entry in TREE])


def test_missing_section_is_rejected():
    data = valid_analysis()
    del data["improvement_idea"]
    with pytest.raises(AnalyzerError, match="missing required sections"):
        validate_analysis(data, [entry["path"] for entry in TREE])


def test_reading_path_must_have_three_to_seven_unique_files():
    data = valid_analysis()
    data["reading_path"] = [{"path": "README.md", "reason": "Start here."}]
    with pytest.raises(AnalyzerError, match="between 3 and 7"):
        validate_analysis(data, [entry["path"] for entry in TREE])


def test_unsupported_flow_does_not_return_speculative_steps():
    data = valid_analysis()
    data["code_flow"] = {"supported": False, "summary": "Insufficient evidence.", "steps": []}
    result = validate_analysis(data, [entry["path"] for entry in TREE])
    assert result["code_flow"]["steps"] == []


def test_when_full_tree_entries_are_available_citations_must_be_files():
    data = valid_analysis()
    data["reading_path"][0]["path"] = "src"
    with pytest.raises(AnalyzerError, match="not present in the supplied GitHub tree"):
        validate_analysis(data, TREE)


def test_repository_map_accepts_directory_inferred_from_tree_paths():
    """GitHub recursive trees can omit explicit directory entries."""
    data = valid_analysis()
    # Deliberately remove the explicit `src` directory entry while retaining
    # actual files below it. The folder remains grounded by those child paths.
    tree_without_src_entry = [entry for entry in TREE if entry["path"] != "src"]
    result = validate_analysis(data, tree_without_src_entry)
    assert result["repository_map"][0]["path"] == "src"


def test_repository_map_rejects_directory_not_supported_by_any_tree_path():
    data = valid_analysis()
    data["repository_map"][0]["path"] = "imaginary-folder"
    with pytest.raises(AnalyzerError, match="not present in the supplied GitHub tree"):
        validate_analysis(data, TREE)
