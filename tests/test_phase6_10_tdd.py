"""Phase 6-10 security and correctness regressions.

These tests are deliberately provider-free: real-service checks are separate
acceptance gates, never replaced by stubbed tests.
"""
import json
import pytest


def _checklist_response():
    task = {'task': 'Locate route', 'file': 'app.py', 'line': 1,
            'why': 'Identify request entry', 'snippet': 'def route():'}
    return {'day_1': [task.copy(), task.copy()],
            'week_1': [{**task, 'task': 'Trace call chain'}],
            'first_contribution': {'task': 'Explore tests', 'files': ['app.py'],
                                   'assumptions': ['Confirm requirements']}}


def test_phase6_duplicate_ai_checklist_tasks_cannot_share_ids():
    from backend.services.onboarding import generate
    response = _checklist_response()
    with pytest.raises(ValueError, match='Duplicate onboarding task'):
        generate({'repo_id': 'o/r', 'revision': 'a'*40,
                  'records': [{'path': 'app.py', 'content': 'def route():\n    pass\n'}]},
                 model=lambda prompt: response)


def test_phase6_onboarding_bounds_untrusted_contribution_content():
    from backend.services.onboarding import generate
    response = _checklist_response()
    response['day_1'] = response['day_1'][:1]
    response['first_contribution']['task'] = 'x'*100000
    with pytest.raises(ValueError, match='contribution'):
        generate({'repo_id': 'o/r', 'revision': 'a'*40,
                  'records': [{'path': 'app.py', 'content': 'def route():\n    pass\n'}]},
                 model=lambda prompt: response)


def test_phase7_safe_exact_python_version_is_not_falsely_reported_vulnerable():
    from backend.services.security_scanner import scan
    result = scan([{'path': 'requirements.txt', 'content': 'flask==3.1.2'}],
        advisory_get=lambda *args, **kwargs: [{
            'ghsa_id': 'GHSA-test', 'severity': 'high',
            'vulnerabilities': [{'package': {'name': 'flask'},
                                 'vulnerable_version_range': '<2.0',
                                 'first_patched_version': '2.0'}]
        }])
    dep = result['dependencies'][0]
    assert dep['check_status'] == 'checked'
    assert dep['advisories'] == []


def test_phase7_unparseable_range_does_not_claim_a_version_is_affected():
    from backend.services.security_scanner import scan
    result = scan([{'path': 'requirements.txt', 'content': 'flask==3.1.2'}],
        advisory_get=lambda *args, **kwargs: [{
            'ghsa_id': 'GHSA-test',
            'vulnerabilities': [{'package': {'name': 'flask'},
                                 'vulnerable_version_range': 'not-a-real-range'}]
        }])
    finding = result['dependencies'][0]['advisories'][0]
    assert finding['status'] == 'version_unverified'
    assert result['coverage']['unverified_advisories'] == 1


def test_phase8_explicit_fastapi_route_to_handler_is_confirmed_by_source():
    from backend.services.code_flow import trace
    source = ('def service():\n    return 1\n\n'
              '@app.get("/items")\n'
              'def items():\n    return service()\n')
    result = trace([{'path': 'api.py', 'content': source}])
    assert result['edges'][0]['from'] == 'route[GET /items]'
    assert result['edges'][0]['to'] == 'api.py:items'
    assert result['edges'][0]['link_type'] == 'CONFIRMED'
    assert result['edges'][0]['line'] == 4
    assert result['edges'][1]['to'] == 'api.py:service'
    assert 'route' in result['mermaid']


def test_phase9_string_instead_of_user_allowlist_cannot_grant_local_access(tmp_path, monkeypatch):
    import backend.github.local_repositories as local
    import backend.core.config as config
    monkeypatch.setenv('REPOLENS_MODEL_PROVIDER', 'ollama')
    monkeypatch.setattr(config, 'EMBEDDING_MODEL', 'ollama:nomic-embed-text')
    folder = tmp_path/'private'; folder.mkdir()
    (folder/'main.py').write_text('def main():\n    pass\n')
    monkeypatch.setenv('REPOLENS_LOCAL_REPOSITORIES', json.dumps({
        'team': {'path': str(folder), 'users': 'alice'}}))
    with pytest.raises(ValueError, match='approved'):
        local.collect('team', 'ali')


def test_phase10_release_gate_requires_reviewed_ai_reports(tmp_path, monkeypatch):
    from scripts import prebuild_gallery as gallery
    monkeypatch.setattr(gallery, 'ROOT', tmp_path)
    with pytest.raises(ValueError, match='reviewed AI reports'):
        gallery.build(min_reviewed=1)


def test_phase10_gallery_escapes_untrusted_markdown_and_keeps_valid_source_links():
    from scripts.prebuild_gallery import render_report
    markdown = ('# Analyzed source\n\n'
                '<script>alert("xss")</script>\n\n'
                '[Evidence](https://github.com/pallets/flask/blob/'+ 'a'*40 + '/src/flask/app.py#L10)\n\n'
                '[Bad](javascript:alert(1))\n')
    html = render_report(markdown)
    assert '<script>' not in html
    assert '&lt;script&gt;' in html
    assert '<a href="https://github.com/pallets/flask/blob/' in html
    assert 'href="javascript:' not in html


def test_phase7_scanner_fetches_omitted_required_manifests(monkeypatch):
    from backend.services import security_scanner as scanner
    import backend.github.github_client as gh
    fetched=[]
    def fetch(owner,repo,path,revision):
        fetched.append((path,revision))
        return 'requests==2.31.0' if path=='requirements.txt' else 'module example.org/demo\ngo 1.22'
    monkeypatch.setattr(gh,'fetch_file_content',fetch)
    monkeypatch.setattr(scanner,'dependency_graph',lambda records:{'nodes':[],'edges':[],'limits':[]})
    captured=[]
    def fake_scan(records, **kwargs):
        captured.extend(records)
        return {'dependencies':[],'patterns':[],'warnings':[],'limits':[], 'coverage':{}}
    monkeypatch.setattr(scanner,'scan',fake_scan)
    result=scanner.scan_repository({'owner':'o','repo':'r','revision':'a'*40,
        'records':[{'path':'src/app.py','content':'pass'}], 'tree':[
            {'path':'src/app.py','size':4}, {'path':'requirements.txt','size':200},
            {'path':'go.mod','size':120}], 'truncated':False})
    assert {r['path'] for r in captured}=={'src/app.py','requirements.txt','go.mod'}
    assert len(fetched)==2 and result['coverage']['resolution_artifacts_fetched']==2


def test_phase10_failed_forced_refresh_preserves_last_approved_report(tmp_path):
    from backend.services import gallery_pipeline as gallery
    root=tmp_path
    repo='pallets/flask'
    path=gallery.state_path(root,repo)
    path.parent.mkdir(parents=True)
    report=path.parent/'report.md'
    report.write_text('An approved source-grounded report')
    state={'repository':repo,'status':'approved','provider':'gemini',
           'model':'gemini-3.5-flash-lite','revision':'a'*40,
           'report_sha256':gallery.digest(report),'manual_review':'approved',
           'reviewer':'tester','reviewed_at':1.0}
    gallery.atomic_json(path,state)
    def fail(*args,**kwargs):
        raise RuntimeError('provider offline')
    results=gallery.generate_ai_reports(root,[repo],force=True,generator=fail)
    assert results[0]['status']=='approved'
    assert results[0]['last_attempt_error']=='RuntimeError'
    assert gallery.read_state(root,repo)['status']=='approved'
    assert gallery.valid_generated(root,repo,gallery.read_state(root,repo))
