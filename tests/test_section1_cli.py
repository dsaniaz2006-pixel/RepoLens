"""CLI-level database schema E2E: real subprocesses, no application credentials."""
import os
import json
import subprocess
import sys
from pathlib import Path


def test_cli_status_upgrade_status_without_leaking_connection_strings(tmp_path):
    project = Path(__file__).resolve().parents[1]
    auth = 'sqlite:///' + str(tmp_path / 'auth.db')
    app = 'sqlite:///' + str(tmp_path / 'app.db')
    env = {**os.environ, 'REPOLENS_AUTH_DATABASE_URL':auth, 'REPOLENS_DATABASE_URL':app}
    def run(action):
        return subprocess.run([sys.executable,'-m','backend.database.schema_migrations',action],
                              cwd=project,env=env,text=True,capture_output=True,check=True)
    before = json.loads(run('status').stdout)
    assert not (tmp_path / 'auth.db').exists() and not (tmp_path / 'app.db').exists()
    assert not before['auth']['up_to_date'] and not before['app']['up_to_date']
    upgrade = run('upgrade')
    assert auth not in upgrade.stdout and app not in upgrade.stdout
    after = json.loads(run('status').stdout)
    assert all(section['up_to_date'] for section in after.values())


def test_cli_verify_exits_nonzero_until_schema_is_upgraded(tmp_path):
    project = Path(__file__).resolve().parents[1]
    env = {**os.environ, 'REPOLENS_AUTH_DATABASE_URL':'sqlite:///'+str(tmp_path/'a.db'),
           'REPOLENS_DATABASE_URL':'sqlite:///'+str(tmp_path/'b.db')}
    cmd = [sys.executable, '-m', 'backend.database.schema_migrations']
    initial = subprocess.run(cmd + ['verify'], cwd=project, env=env, text=True, capture_output=True)
    assert initial.returncode != 0 and 'not current' in initial.stderr
    assert subprocess.run(cmd + ['upgrade'], cwd=project, env=env, capture_output=True).returncode == 0
    assert subprocess.run(cmd + ['verify'], cwd=project, env=env, capture_output=True).returncode == 0
