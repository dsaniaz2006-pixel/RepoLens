"""Test-first Phase 10 publication, approval and navigation invariants.

All fixtures are synthetic and never count as real human-reviewed reports.
"""
import json
from pathlib import Path
import pytest


def _approved(root, repo='pallets/flask'):
    from backend.services.gallery_pipeline import state_path, atomic_json, digest
    state_file = state_path(root, repo)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    report = state_file.parent / 'report.md'
    report.write_text('# AI repository architecture report\n\nRepository: '+repo+'\n\n## 1. Project summary\n\n[Evidence](https://github.com/pallets/flask/blob/'+'a'*40+'/src/flask/app.py#L42)\n')
    state = dict(repository=repo, status='approved', provider='gemini', model='mock',
                 revision='a'*40, report_sha256=digest(report), generated_at=123,
                 manual_review='approved', reviewer='Test reviewer', reviewed_at=123)
    atomic_json(state_file, state)
    return report, state


def test_phase10_landing_links_to_gallery_from_existing_dashboard():
    root = Path(__file__).resolve().parents[1]
    source = (root / 'frontend/src/main.jsx').read_text()
    # The signed-in gallery now uses in-dashboard navigation, not a redirect.
    assert 'GalleryWorkspace' in source
    assert "active('Public Gallery')" in source
    # Anonymous visitors still have an independently reachable public page.
    assert 'href="/gallery/"' in (root / 'frontend/index.html').read_text()
    assert (root / 'frontend/public/gallery/pallets-flask/index.html').is_file()


def test_phase10_published_report_does_not_stay_reviewed_after_approval_revoked(tmp_path, monkeypatch):
    from scripts import prebuild_gallery as script
    from backend.services.gallery_pipeline import publish, state_path, atomic_json
    monkeypatch.setattr(script, 'ROOT', tmp_path)
    report, state = _approved(tmp_path)
    assert publish(tmp_path, ['pallets/flask']) == ['pallets/flask']
    script.build()
    assert 'Reviewed AI architecture report' in (tmp_path/'frontend/public/gallery/pallets-flask/index.html').read_text()
    state['status'] = 'generated'
    state['manual_review'] = 'pending'
    atomic_json(state_path(tmp_path,'pallets/flask'), state)
    script.build()
    assert 'Reviewed AI architecture report' not in (tmp_path/'frontend/public/gallery/pallets-flask/index.html').read_text()


def test_phase10_publication_rejects_unreviewed_report_and_outdated_manifest(tmp_path):
    from backend.services.gallery_pipeline import publish, state_path, atomic_json
    _, state = _approved(tmp_path)
    assert publish(tmp_path, ['pallets/flask']) == ['pallets/flask']
    state['status'] = 'generated'
    atomic_json(state_path(tmp_path,'pallets/flask'), state)
    assert publish(tmp_path, ['pallets/flask']) == []
    manifest = json.loads((tmp_path/'frontend/public/reports/gallery-manifest.json').read_text())
    assert 'pallets/flask' not in manifest


def test_phase10_strict_release_does_not_claim_twenty_unreviewed_reports(tmp_path, monkeypatch):
    from scripts import prebuild_gallery as script
    monkeypatch.setattr(script, 'ROOT', tmp_path)
    _approved(tmp_path)
    from backend.services.gallery_pipeline import publish
    publish(tmp_path,['pallets/flask'])
    with pytest.raises(ValueError, match='reviewed AI reports'):
        script.build(min_reviewed=20)


def test_phase10_gallery_report_exposes_direct_dashboard_cta_and_safe_markdown(tmp_path,monkeypatch):
    from scripts import prebuild_gallery as script
    from backend.services.gallery_pipeline import publish
    monkeypatch.setattr(script,'ROOT',tmp_path)
    _approved(tmp_path)
    publish(tmp_path,['pallets/flask'])
    script.build()
    page=(tmp_path/'frontend/public/gallery/pallets-flask/index.html').read_text()
    assert 'href="/dashboard/"' in page
    assert 'href="/gallery/"' in page
    assert 'rel="noopener noreferrer"' in page
    assert 'Reviewed AI architecture report' in page


def test_phase10_generation_batches_advance_past_provider_failures(tmp_path):
    from scripts.prebuild_gallery import generation_batch
    from backend.services.gallery_pipeline import atomic_json,state_path
    names=['pallets/flask','fastapi/fastapi','django/django']
    atomic_json(state_path(tmp_path,names[0]),{'repository':names[0],'status':'failed'})
    assert generation_batch(tmp_path,names,2)==names[1:]
    assert generation_batch(tmp_path,names,1,force=True)==[names[0]]
