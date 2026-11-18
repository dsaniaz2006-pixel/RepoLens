"""Strict, evidence-driven Phase 11 release gate (never claims live PASS from mocks).

See docs/PHASE_11_VERIFICATION.md. --evidence is a manual/CI attestation file,
not independent verification of hosted services. Empty evidence -> BLOCKED.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CHECKS = {
    'python_suite': 'Full Python suite with no unexplained skips',
    'frontend_unit': 'Frontend unit suite',
    'frontend_build': 'Vite production build',
    'browser_e2e': 'Playwright Chromium real browser suite',
    'backend_http': 'Real HTTP smoke + API authentication',
    'github_action': 'PR Action comment idempotence and permission checks',
    'oauth_real_users': 'Both Google and GitHub real login/logout',
    'authorization_csrf': 'Cross-user, workspace, CSRF and origin negative tests',
    'rag_live': 'Fresh index -> cited chat -> SHA change -> reindex and restart',
    'provider_gemini': 'Live Gemini and quota/retry scenarios',
    'provider_ollama': 'Local Ollama embedding/answer and no cloud fallback',
    'postgres_migration_rollback': 'Real PostgreSQL migrate, backup and rollback rehearsal',
    'backup_restore': 'Local Chroma/auth/job state cold backup and restore',
    'worker_restart': 'Scheduled freshness worker and interrupted-job recovery',
    'repo_cross_language': 'Reviewed pinned Python, JS/TS and Go source evidence',
    'production_https': 'Real HTTPS/TLS, secure cookies, redirect URIs and headers',
    'gallery_publication': '20 intact human-approved reports served publicly',
    'mobile_accessibility': 'Mobile, keyboard/accessibility and error-state checks',
    'end_to_end_journey': '10 features validated together using real accounts/services',
}


def _publication_count(root):
    root = Path(root)
    path = root/'frontend/public/reports/gallery-manifest.json'
    if not path.is_file():
        return 0, 'No reviewed AI gallery manifest found'
    try:
        manifest = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(manifest, dict):
            return 0, 'Invalid gallery manifest'
        from backend.services.gallery_pipeline import publication_receipt
        # Restrict counting to the 20 configured repositories.
        from scripts.prebuild_gallery import REPOSITORIES
        count = sum(publication_receipt(root, repo, manifest) for repo in REPOSITORIES)
        return count, f'{count}/{len(REPOSITORIES)} verified local publication receipts'
    except Exception:
        return 0, 'Gallery manifest/receipts could not be verified'


def evaluate(root=ROOT, evidence=None):
    evidence = evidence or {}
    if not isinstance(evidence, dict):
        raise ValueError('Evidence must be an object keyed by release gate ID')
    checks = {}
    publication_count, publication_note = _publication_count(root)
    for key, description in CHECKS.items():
        raw = evidence.get(key, {})
        if not isinstance(raw, dict):
            raw = {}
        requested = raw.get('status', 'BLOCKED')
        proof = raw.get('evidence')
        if requested not in ('PASS', 'FAIL', 'BLOCKED'):
            requested = 'BLOCKED'
        # An attestation must supply a concrete log, manual walkthrough or record.
        if requested == 'PASS' and (not isinstance(proof, str) or len(proof.strip()) < 10):
            requested = 'BLOCKED'
            proof = None
        note = (proof or 'No verified result supplied') if isinstance(proof, str) else 'No verified result supplied'
        if key == 'gallery_publication':
            if publication_count < 20:
                requested = 'BLOCKED' if requested != 'FAIL' else 'FAIL'
                note = publication_note + '; ' + note
            else:
                note = publication_note + '; ' + note
        checks[key] = {'status': requested, 'description': description, 'evidence': note}
    counts = {status: sum(v['status'] == status for v in checks.values()) for status in ('PASS','FAIL','BLOCKED')}
    status = 'VERIFIED FOR RELEASE' if counts['PASS'] == len(CHECKS) else 'NOT FULLY VERIFIED'
    return {'phase': 11, 'release_status': status, 'generated_utc': datetime.now(timezone.utc).isoformat(),
            'checks': checks, 'counts': counts,
            'disclaimer': 'External evidence values are operator attestations; only local gallery receipts are automatically checked.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, help='JSON map of gate ID -> {status,evidence}; do not include secrets')
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, help='Write report as JSON (default stdout)')
    parser.add_argument('--strict', action='store_true', help='Exit code 2 unless all gates pass')
    args = parser.parse_args(argv)
    source = json.loads(args.evidence.read_text(encoding='utf-8')) if args.evidence else {}
    result = evaluate(args.root, source)
    content = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(content+'\n', encoding='utf-8')
        print(f"Release: {result['release_status']} ({result['counts']}); report: {args.output}")
    else:
        print(content)
    if args.strict and result['release_status'] != 'VERIFIED FOR RELEASE':
        return 2
    return 0

if __name__ == '__main__':
    sys.exit(main())
