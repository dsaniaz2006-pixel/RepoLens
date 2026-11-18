"""Validate and render RepoLens analysis as a Markdown onboarding report."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class ReportError(Exception):
    """Raised when a report cannot safely be generated or saved."""


def _text(value: Any, fallback: str = "Not enough evidence.") -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _paths(values: Any, known_paths: set[str]) -> list[str]:
    if not isinstance(values, list):
        return []
    return [path for path in values if isinstance(path, str) and path in known_paths]


def _code_path(path: str) -> str:
    """Render a repository path as inline code without breaking on backticks."""
    if "`" not in path:
        return f"`{path}`"
    return f"``{path}``"


def render_report(
    analysis: dict[str, Any],
    metadata: dict[str, Any],
    tree_entries: list[dict[str, Any]],
    *,
    tree_truncated: bool = False,
) -> str:
    """Render all required sections, filtering all file citations against tree."""
    if not isinstance(analysis, dict):
        raise ReportError("The analysis result must be an object.")
    if not isinstance(metadata, dict):
        raise ReportError("Repository metadata must be an object.")

    known_paths = {
        entry.get("path")
        for entry in tree_entries
        if isinstance(entry, dict) and isinstance(entry.get("path"), str)
    }
    known_file_paths = {
        entry.get("path")
        for entry in tree_entries
        if isinstance(entry, dict) and entry.get("type") in ("blob", "file")
        and isinstance(entry.get("path"), str)
    }
    # Recursive Git trees can omit explicit folder entries. Prefixes of known
    # paths are valid directory evidence for the repository-map section.
    known_map_paths = set(known_paths)
    for path in known_paths:
        parts = path.split('/')
        known_map_paths.update('/'.join(parts[:i]) for i in range(1, len(parts)))
    repo_name = _text(metadata.get("full_name") or metadata.get("name"), "Unknown repository")
    repo_url = _text(metadata.get("html_url"), "")
    description = _text(metadata.get("description"), "No repository description was provided by GitHub.")

    lines: list[str] = [
        f"# RepoLens Onboarding Report: {repo_name}",
        "",
        f"> Generated from selected source evidence. Repository: {repo_url or repo_name}",
        "",
        "## 1. Project summary",
        "",
        _text(analysis.get("project_summary")),
        "",
        "## 2. Technology stack and evidence",
        "",
    ]
    tech_stack = _items(analysis.get("tech_stack"))
    if tech_stack:
        for item in tech_stack:
            name = _text(item.get("name"), "Unspecified technology")
            explanation = _text(item.get("explanation"))
            evidence = _paths(item.get("evidence_paths"), known_file_paths)
            evidence_text = ", ".join(_code_path(path) for path in evidence) if evidence else "No valid evidence path supplied"
            lines.append(f"- **{name}:** {explanation} Evidence: {evidence_text}.")
    else:
        lines.append("Not enough evidence to identify a technology stack.")
    lines += ["", "## 3. Repository and folder map", ""]
    repository_map = _items(analysis.get("repository_map"))
    if repository_map:
        for item in repository_map:
            path = item.get("path")
            if not isinstance(path, str) or path not in known_map_paths:
                continue
            purpose = _text(item.get("purpose"))
            evidence = _paths(item.get("evidence_paths"), known_file_paths)
            suffix = f" Evidence: {', '.join(_code_path(p) for p in evidence)}." if evidence else ""
            lines.append(f"- {_code_path(path)}: {purpose}{suffix}")
    else:
        lines.append("The available evidence did not support a useful folder map.")

    lines += ["", "## 4. Likely entry points and important files", ""]
    entry_points = _items(analysis.get("entry_points"))
    valid_entry_points = 0
    for item in entry_points:
        path = item.get("path")
        if not isinstance(path, str) or path not in known_file_paths:
            continue
        evidence = _paths(item.get("evidence_paths"), known_file_paths)
        evidence_text = f" Evidence: {', '.join(_code_path(p) for p in evidence)}." if evidence else ""
        lines.append(f"- **{_code_path(path)}:** {_text(item.get('reason'))}.{evidence_text}")
        valid_entry_points += 1
    if not valid_entry_points:
        lines.append("No likely entry point could be verified from the supplied tree.")

    lines += ["", "## 5. Recommended reading path", ""]
    reading_path = _items(analysis.get("reading_path"))
    valid_reading_count = 0
    for index, item in enumerate(reading_path, start=1):
        path = item.get("path")
        if not isinstance(path, str) or path not in known_file_paths:
            continue
        lines.append(f"{valid_reading_count + 1}. **{_code_path(path)}**: {_text(item.get('reason'))}")
        valid_reading_count += 1
        if valid_reading_count >= 7:
            break
    if valid_reading_count == 0:
        lines.append("Not enough evidence to recommend a reading path.")
    elif valid_reading_count < 3:
        lines.append("\n> Note: fewer than three valid reading-path files remained after checking cited paths against the repository tree.")

    lines += ["", "## 6. Representative code/request flow", ""]
    code_flow = analysis.get("code_flow")
    if isinstance(code_flow, dict) and code_flow.get("supported") is True:
        summary = _text(code_flow.get("summary"), "A flow was identified, but its summary was not supplied.")
        lines += [summary, ""]
        valid_steps = 0
        for index, step in enumerate(_items(code_flow.get("steps")), start=1):
            path = step.get("path")
            if not isinstance(path, str) or path not in known_file_paths:
                continue
            lines.append(f"{index}. **{_code_path(path)}**: {_text(step.get('role'))}. Evidence: {_text(step.get('evidence'))}")
            valid_steps += 1
        if valid_steps == 0:
            lines.append("The flow was marked supported, but no steps with valid paths were available. Treat it as unverified.")
    else:
        lines.append("A representative flow is omitted because the available source evidence does not confirm the connections.")

    lines += ["", "## 7. Evidence-based improvement idea", ""]
    idea = analysis.get("improvement_idea")
    if isinstance(idea, dict):
        lines.append(_text(idea.get("idea")))
        evidence = _paths(idea.get("evidence_paths"), known_file_paths)
        lines.append("")
        lines.append("**Evidence:** " + (", ".join(_code_path(path) for path in evidence) if evidence else "No valid evidence path supplied."))
        assumptions = idea.get("assumptions") if isinstance(idea.get("assumptions"), list) else []
        lines.append("**Assumptions:** " + ("; ".join(str(value) for value in assumptions if str(value).strip()) if assumptions else "None stated."))
    else:
        lines.append("No improvement idea was returned.")

    lines += ["", "## 8. Limitations and uncertain findings", ""]
    limitations = analysis.get("limitations")
    limitations_list = [str(item).strip() for item in limitations if str(item).strip()] if isinstance(limitations, list) else []
    if tree_truncated:
        limitations_list.insert(0, "GitHub returned a truncated recursive tree. The bounded fallback may omit nested files, so the repository map is incomplete.")
    if limitations_list:
        lines.extend(f"- {limitation}" for limitation in limitations_list)
    else:
        lines.append("The model did not supply additional limitations. Absence of a limitation does not guarantee completeness.")
    lines += [
        "",
        "---",
        "",
        "## Repository metadata",
        "",
        f"- **Name:** {repo_name}",
        f"- **GitHub description:** {description}",
        f"- **Primary language reported by GitHub:** {_text(metadata.get('language'), 'Unknown')}",
        f"- **Tree paths available to analysis:** {len(known_paths)}",
        f"- **Tree completeness:** {'Incomplete (truncated fallback used)' if tree_truncated else 'Recursive tree response was not marked truncated'}",
        "",
        "*RepoLens uses selected repository text as evidence. AI explanations can be incomplete or wrong and should be checked against the source.*",
        "",
    ]
    return "\n".join(lines)


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip(".-_")
    return slug or "repository"


def save_report(
    analysis: dict[str, Any],
    metadata: dict[str, Any],
    tree_entries: list[dict[str, Any]],
    owner: str,
    repo: str,
    *,
    output_dir: str | Path = "reports",
    overwrite: bool = False,
    tree_truncated: bool = False,
) -> Path:
    """Render and save `reports/<owner>-<repo>-report.md` safely.

    Existing reports are refused unless ``overwrite=True`` is explicitly set.
    """
    report_text = render_report(analysis, metadata, tree_entries, tree_truncated=tree_truncated)
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{_safe_slug(owner)}-{_safe_slug(repo)}-report.md"
    if target.exists() and not overwrite:
        raise ReportError(
            f"Report already exists at {target}. Move it or remove it before running again; "
            "RepoLens will not overwrite a previous report silently."
        )
    try:
        if overwrite:
            target.write_text(report_text, encoding="utf-8")
        else:
            # Exclusive creation also protects against a report appearing between
            # the existence check and the write.
            with target.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(report_text)
    except FileExistsError as exc:
        raise ReportError(f"Report already exists at {target}; no file was overwritten.") from exc
    except OSError as exc:
        raise ReportError(f"Could not save report to {target} ({type(exc).__name__}).") from exc
    return target
