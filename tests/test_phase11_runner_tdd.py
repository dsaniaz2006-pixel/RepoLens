"""Phase 11 test-first acceptance for local verification evidence orchestration."""
from pathlib import Path
import json
import pytest


def test_release_runner_refuses_to_label_skipped_python_suite_as_pass():
    from scripts.phase11_verify import classify
    assert classify('python_suite', 0, '287 passed, 1 skipped in 40.1s') == 'BLOCKED'
    assert classify('python_suite', 0, '288 passed in 40.1s') == 'PASS'
    assert classify('python_suite', 1, '287 passed, 1 failed') == 'FAIL'
    assert classify('frontend_unit', 0, '1 skipped (unrelated text)') == 'PASS'


def test_release_runner_evidence_only_covers_gates_actually_run():
    from scripts.phase11_verify import build_evidence
    evidence = build_evidence({'frontend_build': {'status':'PASS','exit_code':0,
        'command':'npm run build','log':'/tmp/build.log','skip_count_detected':False}},'2026-11-12T00:00:00Z')
    assert set(evidence) == {'frontend_build'}
    assert evidence['frontend_build']['status'] == 'PASS'
    assert 'npm run build' in evidence['frontend_build']['evidence']
    assert 'oauth_real_users' not in evidence


def test_runner_can_execute_a_real_local_command_and_capture_private_log(tmp_path, monkeypatch):
    import sys
    from scripts import phase11_verify as runner
    (tmp_path/'frontend').mkdir()
    monkeypatch.setattr(runner,'command_for',lambda name: [sys.executable,'-c','print("local verified")'])
    output=tmp_path/'private-reports';output.mkdir(mode=0o700)
    result=runner.run_one('frontend_unit',output,root=tmp_path)
    assert result['status']=='PASS'
    assert Path(result['log']).read_text().strip()=='local verified'
    assert Path(result['log']).stat().st_mode & 0o077 == 0


def test_phase11_release_docs_and_version_are_present():
    root=Path(__file__).resolve().parents[1]
    assert (root/'docs/PHASE_11_VERIFICATION.md').is_file()
    assert (root/'docs/FINAL_RELEASE_VERIFICATION.md').is_file()
    assert (root/'VERSION').read_text().strip() == '1.1.0-rc.1'


def test_release_runner_cli_writes_a_real_gate_report(tmp_path):
    import subprocess,sys
    root=Path(__file__).resolve().parents[1]
    output=tmp_path/'run'
    result=subprocess.run([sys.executable,str(root/'scripts/phase11_verify.py'),
        '--only','action_unit','--output-dir',str(output)],cwd=root,capture_output=True,text=True)
    assert result.returncode == 0, result.stdout+result.stderr
    summary=json.loads((output/'run-summary.json').read_text())
    gate=json.loads((output/'release-gate.json').read_text())
    assert summary['action_unit']['status']=='PASS'
    assert gate['release_status']=='NOT FULLY VERIFIED'
    assert gate['checks']['oauth_real_users']['status']=='BLOCKED'
    assert gate['checks']['gallery_publication']['status']=='BLOCKED'
