"""Run Phase 11 LOCAL automated checks and capture honest release-gate evidence.

These checks use local/synthetic services and cannot prove real OAuth, Gemini,
Ollama, public TLS, live GitHub Action execution or reviewed gallery reports.
Do not commit the generated private log files or evidence to version control.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
FRONTEND = ROOT / 'frontend'
GATES = ('python_suite', 'frontend_unit', 'frontend_build', 'browser_e2e', 'backend_http')
STEPS = ('preflight',) + GATES + ('action_unit',)


def command_for(name, python=None):
    python = python or sys.executable
    return {
        'preflight': [python, 'scripts/phase0_preflight.py'],
        'python_suite': [python, '-m', 'pytest', '-q', '-ra'],
        'frontend_unit': ['npm', 'test'],
        'frontend_build': ['npm', 'run', 'build'],
        'browser_e2e': ['npm', 'run', 'test:browser'],
        'backend_http': [python, 'scripts/verify_release_http.py'],
        'action_unit': ['node', '--test', 'tests-js/pr_comment.test.mjs'],
    }[name]


def classify(name, exit_code, output):
    """PASS only for an exit-0 command; unexplained Python skips BLOCK its gate."""
    if exit_code != 0:
        return 'FAIL'
    if name == 'python_suite' and re.search(r'\b[1-9][0-9]*\s+skipped\b', output):
        return 'BLOCKED'
    return 'PASS'


def run_one(name, output_dir, *, root=ROOT):
    cwd = root / 'frontend' if name in ('frontend_unit', 'frontend_build', 'browser_e2e') else root
    command = command_for(name)
    log_path = output_dir / f'{name}.log'
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    fd = os.open(log_path, flags, 0o600)
    text = ''
    status_code = 127
    print(f'\n--- {name}: {" ".join(command)} ---', flush=True)
    with os.fdopen(fd, 'w', encoding='utf-8') as log:
        try:
            process = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in process.stdout:
                print(line, end='', flush=True)
                log.write(line)
                text += line  # test summaries only; full log is retained for diagnostics
            status_code = process.wait()
        except OSError as exc:
            text = f'Failed to execute {command[0]}: {type(exc).__name__}'
            print(text, flush=True)
            log.write(text+'\n')
    status = classify(name, status_code, text)
    return {'status': status, 'exit_code': status_code, 'log': str(log_path),
            'command': ' '.join(command), 'skip_count_detected': bool(re.search(r'\b[1-9][0-9]*\s+skipped\b', text))}


def build_evidence(results, date):
    evidence = {}
    for key in GATES:
        if key not in results:
            continue
        item = results[key]
        evidence[key] = {'status': item['status'],
                         'evidence': f"{date}: {item['command']} -> exit {item['exit_code']}; "
                                     f"local test log {item['log']}" +
                                     (' (pytest contains skipped tests; review before PASS)' if item['skip_count_detected'] else '')}
    return evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', nargs='+', choices=STEPS, help='Run selected checks; others remain BLOCKED')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'reports' / 'phase11-local')
    parser.add_argument('--operator-evidence', type=Path,
                        help='Optional manually verified gates; never share credentials or PII')
    args = parser.parse_args(argv)
    out = args.output_dir.resolve()
    if out.exists() and any(out.iterdir()):
        # Avoid overwriting previous evidence. Each run should use a fresh directory.
        parser.error(f'Output directory must be empty or new: {out}')
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    out.chmod(0o700)
    chosen = args.only or STEPS
    results = {name: run_one(name, out) for name in chosen}
    now = datetime.now(timezone.utc).isoformat()
    local = build_evidence(results, now)
    operator = {}
    if args.operator_evidence:
        operator = json.loads(args.operator_evidence.read_text(encoding='utf-8'))
        if not isinstance(operator, dict):
            parser.error('Operator evidence must be a JSON object')
        # Never let manual attestation override an automated failure/skip.
    from scripts.phase11_gate import evaluate
    report = evaluate(ROOT, {**operator, **local})
    for filename, payload in (('run-summary.json', results),('local-evidence.json', local),
                              ('release-gate.json', report)):
        path = out / filename
        with path.open('x', encoding='utf-8') as file:
            json.dump(payload, file, indent=2)
            file.write('\n')
        path.chmod(0o600)
    print(f"\nPhase 11 local: {sum(v['status']=='PASS' for v in results.values())}/{len(results)} PASS; "
          f"release: {report['release_status']} ({report['counts']})")
    print(f'Private logs and gate report: {out}')
    return 1 if any(item['status'] != 'PASS' for item in results.values()) else 0


if __name__ == '__main__':
    raise SystemExit(main())
