"""Phase 11 red/green release, backup, and publication regression tests."""
import json
import zipfile
from pathlib import Path
import pytest


def test_offline_backup_restore_is_verified_and_does_not_overwrite(tmp_path):
    from scripts.phase11_state import backup, verify, restore
    source = tmp_path / 'runtime'
    (source/'auth').mkdir(parents=True)
    (source/'chroma').mkdir()
    (source/'auth'/'accounts.sqlite3').write_bytes(b'accounts for regression')
    (source/'chroma'/'index.bin').write_bytes(b'vector data')
    archive = tmp_path/'backup.zip'
    backup({'auth':source/'auth','chroma':source/'chroma'},archive)
    result = verify(archive)
    assert result['valid'] is True and result['files'] == 2
    target = tmp_path/'restored'
    restore(archive,target)
    assert (target/'auth'/'accounts.sqlite3').read_bytes() == b'accounts for regression'
    assert (target/'chroma'/'index.bin').read_bytes() == b'vector data'
    with pytest.raises(FileExistsError):restore(archive,target)


def test_backup_detects_tampering_and_rejects_traversal(tmp_path):
    from scripts.phase11_state import backup,verify,restore
    state = tmp_path/'auth';state.mkdir();(state/'accounts.sqlite3').write_text('hello')
    original=tmp_path/'original.zip';backup({'auth':state},original)
    with zipfile.ZipFile(original) as inp, zipfile.ZipFile(tmp_path/'forged.zip','w') as out:
        for member in inp.namelist():
            body=inp.read(member)
            if member.endswith('accounts.sqlite3'): body=b'tampered'
            out.writestr(member,body)
    with pytest.raises(ValueError,match='SHA-256|checksum'):verify(tmp_path/'forged.zip')
    with pytest.raises(ValueError):restore(tmp_path/'forged.zip',tmp_path/'target')
    with zipfile.ZipFile(tmp_path/'traversal.zip','w') as out:
        out.writestr('../outside.txt','malicious')
        out.writestr('manifest.json','{}')
    with pytest.raises(ValueError):verify(tmp_path/'traversal.zip')
    assert not (tmp_path/'outside.txt').exists()


def test_backup_rejects_symlinks_and_private_state_not_in_release(tmp_path):
    from scripts.phase11_state import backup
    from scripts.package_release import package
    root=tmp_path/'project';root.mkdir()
    (root/'auth').mkdir();(root/'auth'/'secret.key').write_text('secret-content')
    (root/'auth'/'link').symlink_to(root/'auth'/'secret.key')
    with pytest.raises(ValueError,match='symlink'):backup({'auth':root/'auth'},tmp_path/'backup.zip')
    (root/'auth'/'link').unlink()
    (root/'frontend/public').mkdir(parents=True)
    (root/'frontend/public/reports').mkdir()
    (root/'frontend/public/reports/good.md').write_text('public')
    (root/'data/private').mkdir(parents=True)
    (root/'data/private/token.txt').write_text('very private')
    (root/'evaluation/checkpoints').mkdir(parents=True)
    (root/'evaluation/checkpoints/snapshot.gz').write_bytes(b'private state')
    (root/'api.py').write_text('print(1)')
    package(root,tmp_path/'source.zip')
    with zipfile.ZipFile(tmp_path/'source.zip') as archive:
        names=set(archive.namelist())
        assert 'RepoLens/frontend/public/reports/good.md' in names
        assert 'RepoLens/api.py' in names
        assert not any('secret.key' in name or '/data/' in name or 'checkpoints/' in name for name in names)


def test_release_gate_blocks_missing_live_evidence_and_gallery(tmp_path):
    from scripts.phase11_gate import evaluate
    result=evaluate(tmp_path,{})
    assert result['release_status']=='NOT FULLY VERIFIED'
    assert result['checks']['gallery_publication']['status']=='BLOCKED'
    assert result['checks']['oauth_real_users']['status']=='BLOCKED'
    assert result['checks']['production_https']['status']=='BLOCKED'
    assert result['checks']['browser_e2e']['status']=='BLOCKED'


def test_release_gate_requires_gallery_approval_and_check_evidence(tmp_path):
    from scripts.phase11_gate import evaluate
    asset=tmp_path/'frontend/public/reports';asset.mkdir(parents=True)
    (asset/'gallery-manifest.json').write_text(json.dumps({f'o/r{i}':{'type':'reviewed_ai_report'} for i in range(20)}))
    result=evaluate(tmp_path,{'gallery_publication':{'status':'PASS','evidence':'approved 20 on actual public origin'},'production_https':{'status':'PASS','evidence':'curl audit from public host'}})
    # A manifest listing reports alone cannot satisfy a real source/review/deployment gate.
    assert result['checks']['gallery_publication']['status']!='PASS'
    assert result['checks']['production_https']['status']=='PASS'
    assert result['release_status']=='NOT FULLY VERIFIED'


def test_release_gate_does_not_accept_pass_without_evidence(tmp_path):
    from scripts.phase11_gate import evaluate
    result=evaluate(tmp_path,{'oauth_real_users':{'status':'PASS'},'browser_e2e':{'status':'PASS','evidence':'14 passed on real mac'}})
    assert result['checks']['oauth_real_users']['status']=='BLOCKED'
    assert result['checks']['browser_e2e']['status']=='PASS'


def test_production_auth_security_headers_static_source():
    # This is complemented by a real ASGI/HTTP test when auth dependencies are installed.
    from pathlib import Path
    source=(Path(__file__).resolve().parents[1]/'backend/auth/auth.py').read_text()
    assert 'Strict-Transport-Security' in source
    assert 'X-Frame-Options' in source
    assert 'Permissions-Policy' in source
    assert 'TrustedHostMiddleware' in source
