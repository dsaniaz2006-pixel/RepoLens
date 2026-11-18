"""Reproducible, honest RepoLens verification for three real GitHub projects.

No network or API calls unless --live is explicitly supplied. Live calls may
consume GitHub/Gemini quotas. A structural pass is NOT a human accuracy check.
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.ai.analyzer import validate_analysis, AnalyzerError
from backend.services.report import render_report

DEFAULT_REPOS = [
    'https://github.com/pallets/flask',
    'https://github.com/axios/axios',
    'https://github.com/pallets/markupsafe',
]


def audit_result(result: dict) -> dict:
    """Check structured evidence references and generated Markdown sections."""
    analysis = result['analysis']
    tree = result['tree']
    metadata = result['metadata']
    manifest = result.get('evidence_paths')
    verified = validate_analysis(analysis, tree, set(manifest) if manifest is not None else None)
    body = render_report(verified, metadata, tree, tree_truncated=bool(result.get('truncated')))
    required = [
        '## 1. Project summary', '## 2. Technology stack',
        '## 3. Repository and folder map', '## 4. Likely entry points',
        '## 5. Recommended reading path', '## 6. Representative',
        '## 7. Evidence-based improvement', '## 8. Limitations',
    ]
    missing = [section for section in required if section not in body]
    file_paths = {r['path'] for r in tree if r.get('type') in ('blob', 'file')}
    path_refs = [p for block in verified.get('tech_stack', []) for p in block['evidence_paths']]
    path_refs += [x['path'] for x in verified['reading_path']]
    path_refs += [p for block in verified.get('entry_points', []) for p in block['evidence_paths']]
    path_refs += list(verified.get('improvement_idea', {}).get('evidence_paths', []))
    missing_files = sorted(set(path_refs) - file_paths)
    return {
        'passed': not missing and not missing_files,
        'report_sections_missing': missing,
        'invalid_file_references': missing_files,
        'tree_files': len(file_paths),
        'tree_truncated': bool(result.get('truncated')),
        'reading_path_count': len(verified['reading_path']),
        'evidence_path_references_checked': len(path_refs),
        'source_manifest_available': manifest is not None,
        'human_review': 'NOT VERIFIED: inspect the claims and flow in actual source files',
    }


def run_live(repo_url: str, output_dir: Path) -> dict:
    from backend.services.pipeline import generate_report
    try:
        data = generate_report(repo_url, output_dir=str(output_dir), overwrite=True, capture_evidence=True)
        checks = audit_result(data)
        return {
            'repository': repo_url, 'status': 'automated_structural_pass' if checks['passed'] else 'automated_structural_fail',
            'report_path': str(data['report_path']), 'revision': data['revision'], 'checks': checks,
            'manual_accuracy_review': 'PENDING',
            'observed_failure': '', 'fix': '', 'retest_result': 'PENDING',
        }
    except Exception as exc:
        # Never write exception text to log: SDK exceptions may include sensitive values.
        return {'repository': repo_url, 'status': 'live_run_failed',
                'error_type': type(exc).__name__, 'manual_accuracy_review': 'PENDING',
                'observed_failure': 'Inspect local terminal logs (do not share secrets)',
                'fix': 'PENDING', 'retest_result': 'PENDING'}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Audit RepoLens reports; explicitly opt in to live API calls.')
    parser.add_argument('--live', action='store_true', help='Run GitHub and Gemini live (may incur API charges).')
    parser.add_argument('--repos', nargs='+', default=DEFAULT_REPOS, help='Repository URLs; include three different repositories.')
    parser.add_argument('--output-dir', type=Path, default=ROOT/'reports'/'evaluation')
    args = parser.parse_args(argv)
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=ROOT / '.env', override=False)
    if not args.live:
        print('NOT RUN: add --live to contact GitHub and Gemini; live results are not verified.')
        print('Target repositories:', ', '.join(args.repos))
        return 0
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = [run_live(repo, args.output_dir) for repo in args.repos]
    payload = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
               'live_executed': True, 'human_accuracy_verified': False,
               'results': results}
    dest = args.output_dir/'evaluation-results.json'
    dest.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    for result in results:
        print(f"{result['repository']}: {result['status']}")
    print('Saved structural results and outstanding human checks to', dest)
    return 0 if all(r['status']=='automated_structural_pass' for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
