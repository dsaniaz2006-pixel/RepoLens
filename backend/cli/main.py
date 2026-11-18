"""RepoLens CLI: inspect a public repository and save an evidence-based report."""

from __future__ import annotations

import argparse
import sys

from backend.core.environment import load_project_environment
load_project_environment()

from backend.ai.analyzer import AnalyzerError, analyze_repository
from backend.core.config import MAX_FILES, TOTAL_CONTEXT_BUDGET
from backend.services.file_selector import filter_and_rank, selection_audit
from backend.github.github_client import (
    GitHubError,
    RateLimitError,
    RepoNotFoundError,
    collect_selected_file_contents,
    fetch_repo_metadata,
    fetch_tree,
    parse_github_url,
)
from backend.services.report import ReportError, save_report



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze a public GitHub repository and write an onboarding report."
    )
    parser.add_argument(
        "url",
        help="Public GitHub repository URL, e.g. https://github.com/pallets/flask",
    )
    parser.add_argument(
        "--output-dir",
        default="reports",
        help="Directory for the Markdown report (default: reports).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Explicitly allow replacing an existing report for this repository.",
    )
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--pr', type=int, help='Analyze a pull request without executing its code')
    actions.add_argument('--compare', nargs=2, metavar=('BASE','HEAD'), help='Analyze changes between refs')
    parser.add_argument('--output', help='Write PR impact Markdown to this file')
    actions.add_argument('--interview', action='store_true', help='Five source-backed interview questions')
    actions.add_argument('--contribution', action='store_true', help='Candidate beginner contribution with risks')
    actions.add_argument('--index', action='store_true', help='Build revision-specific local RAG index')
    actions.add_argument('--ask', metavar='QUESTION', help='Ask a question from the current indexed revision')
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        owner, repo = parse_github_url(args.url)
    except ValueError as exc:
        print(f"Invalid repository URL: {exc}", file=sys.stderr)
        return 2

    if args.pr is not None or args.compare:
        try:
            from backend.services.pr_analysis import analyze_diff, markdown
            from pathlib import Path
            result=analyze_diff(args.url,pr=args.pr,base=args.compare[0] if args.compare else None,head=args.compare[1] if args.compare else None)
            text=markdown(result)
            if args.output: Path(args.output).write_text(text,encoding='utf-8')
            else: print(text)
            return 0
        except (ValueError,GitHubError) as exc:
            print(str(exc),file=sys.stderr);return 1

    if args.interview or args.contribution:
        try:
            from backend.services.pipeline import collect_repo
            from backend.ai.extra_modes import interview_mode, contribution_mode
            import json
            data = collect_repo(args.url)
            result = interview_mode(data['metadata'], data['records']) if args.interview else contribution_mode(data['metadata'], data['records'])
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        except (GitHubError, AnalyzerError, ValueError) as exc:
            print(f'RepoLens error: {exc}', file=sys.stderr)
            return 1

    if args.index or args.ask is not None:
        try:
            from backend.services.pipeline import index_repo, ask_repo
            import json
            result = index_repo(args.url) if args.index else ask_repo(args.url, args.ask)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        except Exception as exc:
            from backend.rag.embeddings import EmbeddingError
            from backend.rag.rag_store import StoreError
            from backend.ai.qa import QAError
            if isinstance(exc, (GitHubError, AnalyzerError, EmbeddingError, StoreError, QAError, ValueError)):
                print(f'RepoLens error: {exc}', file=sys.stderr)
                return 1
            raise

    print(f"RepoLens: analyzing {owner}/{repo}")
    try:
        metadata = fetch_repo_metadata(owner, repo)
        if metadata.get("private"): raise ValueError("Only public repositories are supported")
        print(f"Default branch: {metadata['default_branch']}")

        tree_entries, tree_truncated = fetch_tree(owner, repo, metadata["default_branch"])
        if not tree_entries:
            raise GitHubError("The GitHub tree contained no usable paths.")
        selected = filter_and_rank(tree_entries)
        audit = selection_audit(tree_entries, selected)
        print(f"Tree paths received: {len(tree_entries)}")
        print(f"Selected files ({len(selected)}, cap {MAX_FILES}):")
        for item in audit:
            if item["decision"] == "selected":
                print(f"  {item['path']} (score {item['score']}): {item['reason']}")

        collected = collect_selected_file_contents(
            owner, repo, metadata["default_branch"], selected, tree_entries
        )
        usable = [item for item in collected if not item["skipped"] and item.get("content")]
        total_chars = sum(item.get("included_char_count", 0) for item in usable)
        print(f"Selected contents collected: {len(usable)} file(s), {total_chars}/{TOTAL_CONTEXT_BUDGET} characters")
        if not usable:
            reasons = [item.get("skip_reason") for item in collected if item.get("skip_reason")]
            detail = reasons[0] if reasons else "No text files passed the selection and content checks."
            raise GitHubError(f"No usable text content could be collected. {detail}")

        analysis = analyze_repository(
            metadata,
            tree_entries,
            usable,
            tree_truncated=tree_truncated,
        )
        path = save_report(
            analysis,
            metadata,
            tree_entries,
            owner,
            repo,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
            tree_truncated=tree_truncated,
        )
        print(f"\nReport saved: {path}")
        print("Review the report against source files before relying on its conclusions.")
        return 0

    except RepoNotFoundError:
        print(f"Repository or selected file not found: {owner}/{repo}", file=sys.stderr)
        return 1
    except RateLimitError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (GitHubError, AnalyzerError, ReportError) as exc:
        print(f"RepoLens error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
