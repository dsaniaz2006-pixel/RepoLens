"""Offline authentication tests; real provider consent is explicitly not simulated as live verification."""
import base64
import hashlib
import json
import time
from urllib.parse import parse_qs, urlsplit
import httpx
from authlib.integrations.httpx_client import oauth2_client
# Match the HTTP transport used by the installed Authlib release.
httpx = getattr(oauth2_client, 'httpx2', httpx)
import pytest
from authlib.jose import JsonWebKey, jwt
from fastapi.testclient import TestClient
from backend.auth.auth import AuthManager, COOKIE
from backend.api.api import app


@pytest.mark.parametrize('path', ['/api/history','/api/report/a/b','/api/report/a/b/pdf','/api/config-status'])
def test_api_requires_real_session(auth_manager, path):
    client = TestClient(app)
    assert client.get(path).status_code == 401
    client.cookies.set(COOKIE, 'forged-token')
    assert client.get(path).status_code == 401


@pytest.mark.parametrize('path', ['/api/analyze','/api/index','/api/ask','/api/interview','/api/contribution'])
def test_api_mutations_require_session(auth_manager, path):
    assert TestClient(app).post(path, json={'url':'https://github.com/a/b','question':'why'}).status_code == 401


@pytest.mark.parametrize('path', ['/dashboard','/dashboard/','/dashboard/index.html','/docs','/openapi.json','/%64ashboard/index.html','/foo/%2e%2e/dashboard/index.html'])
def test_workspace_direct_urls_redirect(auth_manager, path):
    response = TestClient(app).get(path, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers['location'] == '/login/'


def test_session_me_expiry_and_logout(auth_manager, signed_in_client):
    client = signed_in_client
    me = client.get('/api/auth/me')
    assert me.status_code == 200 and me.json()['user']['name'] == 'Test user'
    assert 'no-store' in me.headers['cache-control']
    token = client.cookies.get(COOKIE)
    with auth_manager.connect() as db:
        row = db.execute('SELECT token_hash FROM sessions').fetchone()
        assert row['token_hash'] != token
    response = client.post('/api/auth/logout')
    assert response.status_code == 200
    assert auth_manager.authenticate(token) is None
    assert client.get('/api/history').status_code == 401
    new_token = auth_manager.new_session(me.json()['user']['id'])
    with auth_manager.connect() as db:
        db.execute('UPDATE sessions SET expires_at=?', (int(time.time())-1,))
    assert auth_manager.authenticate(new_token) is None


def test_csrf_and_origin_validation(signed_in_client):
    client = signed_in_client
    assert client.post('/api/auth/logout', headers={'X-CSRF-Token':'wrong'}).status_code == 403
    assert client.post('/api/auth/logout', headers={'Origin':'https://attacker.example'}).status_code == 403
    client.headers.pop('X-CSRF-Token')
    assert client.post('/api/analyze', json={'url':'https://github.com/a/b'}).status_code == 403
    assert client.post('/api/auth/logout').status_code == 403


def test_accounts_not_merged_by_email(auth_manager):
    a = auth_manager.upsert_user('google','same','A','same@example.com')
    b = auth_manager.upsert_user('github','same','B','same@example.com')
    assert a['id'] != b['id']
    assert auth_manager.upsert_user('google','same','New A')['id'] == a['id']


def test_report_history_and_downloads_are_user_scoped(auth_manager, signed_in_client):
    import backend.api.api as api
    first = signed_in_client.get('/api/auth/me').json()['user']
    directory = api.REPORT_DIR/'users'/first['id']; directory.mkdir(parents=True)
    (directory/'a-b-analysis.json').write_text(json.dumps({'metadata':{'full_name':'a/b'}}))
    (directory/'a-b-report.md').write_text('# Private report')
    assert len(signed_in_client.get('/api/history').json()) == 1
    assert signed_in_client.get('/api/report/a/b').status_code == 200
    second = auth_manager.upsert_user('github','456','Other')
    other = TestClient(app);other.cookies.set(COOKIE, auth_manager.new_session(second['id']))
    assert other.get('/api/history').json() == []
    assert other.get('/api/history/a/b').status_code == 404
    assert other.get('/api/report/a/b').status_code == 404
    assert other.get('/api/report/a/b/pdf').status_code == 404


def test_provider_not_configured_is_honest(auth_manager):
    client=TestClient(app)
    assert client.get('/api/auth/providers').json()['providers'] == {'google':False,'github':False}
    assert client.get('/api/auth/login/github',follow_redirects=False).headers['location'] == '/login/?error=provider_unavailable'
    assert client.get('/api/auth/login/unknown').status_code == 404
    assert client.get('/api/auth/callback/google?code=forged',follow_redirects=False).headers['location'].startswith('/login/?error=')
    assert client.get('/api/auth/me').status_code == 401


@pytest.mark.parametrize('env', [
 {'REPOLENS_ENV':'production','REPOLENS_BASE_URL':'https://app.example'},
 {'REPOLENS_ENV':'production','REPOLENS_BASE_URL':'http://app.example','REPOLENS_SESSION_SECRET':'a'*40},
 {'REPOLENS_BASE_URL':'https://app.example/evil'},
 {'REPOLENS_BASE_URL':'https://user:password@app.example'},
])
def test_insecure_configuration_rejected(tmp_path, env):
    with pytest.raises(ValueError):AuthManager(directory=tmp_path/'auth',environ=env)


@pytest.fixture
def configured_auth(tmp_path, monkeypatch):
    manager=AuthManager(directory=tmp_path/'oauth', environ={
        'REPOLENS_BASE_URL':'https://127.0.0.1:5173',
        'GOOGLE_CLIENT_ID':'test-google','GOOGLE_CLIENT_SECRET':'test-secret',
        'GITHUB_CLIENT_ID':'test-github','GITHUB_CLIENT_SECRET':'test-secret',
    })
    monkeypatch.setattr(app.state,'auth',manager)
    return manager


def github_transport(request):
    if request.url.path == '/login/oauth/access_token':
        form=parse_qs(request.content.decode())
        assert form['code_verifier']
        assert form['client_id'] == ['test-github'] and form['client_secret'] == ['test-secret']
        assert form['redirect_uri'] == ['https://127.0.0.1:5173/api/auth/callback/github']
        return httpx.Response(200,json={'access_token':'provider-test-token','token_type':'Bearer','scope':'read:user user:email'})
    if request.url.path == '/user':return httpx.Response(200,json={'id':789,'login':'octocat','name':'Octocat'})
    if request.url.path == '/user/emails':return httpx.Response(200,json=[{'email':'a@example.com','primary':True,'verified':True}])
    raise AssertionError(str(request.url))


def test_github_signup_returning_login_and_cookie_security(configured_auth):
    remote=configured_auth.oauth.create_client('github')
    remote.client_kwargs['transport']=httpx.MockTransport(github_transport)
    client=TestClient(app, base_url="https://127.0.0.1:5173")
    ids=[];tokens=[]
    for _ in range(2):
        begin=client.get('/api/auth/login/github',follow_redirects=False)
        assert begin.status_code == 302
        q=parse_qs(urlsplit(begin.headers['location']).query)
        assert q['code_challenge_method'] == ['S256'] and q['state']
        done=client.get('/api/auth/callback/github',params={'code':'example','state':q['state'][0]},follow_redirects=False)
        assert done.headers['location'] == '/dashboard/'
        cookie=done.headers['set-cookie']
        assert 'HttpOnly' in cookie and 'SameSite=lax' in cookie
        ids.append(client.get('/api/auth/me').json()['user']['id'])
        tokens.append(client.cookies.get(COOKIE))
    assert ids[0] == ids[1]
    assert tokens[0] != tokens[1]
    assert configured_auth.authenticate(tokens[0]) is None


def test_github_state_tampering_replay_and_provider_denial(configured_auth):
    remote=configured_auth.oauth.create_client('github')
    remote.client_kwargs['transport']=httpx.MockTransport(github_transport)
    client=TestClient(app, base_url="https://127.0.0.1:5173")
    start=client.get('/api/auth/login/github',follow_redirects=False)
    state=parse_qs(urlsplit(start.headers['location']).query)['state'][0]
    bad=client.get('/api/auth/callback/github?code=forged&state=wrong',follow_redirects=False)
    assert bad.headers['location'] == '/login/?error=signin_failed'
    assert client.get('/api/auth/me').status_code == 401
    denied=client.get('/api/auth/callback/github?error=access_denied',follow_redirects=False)
    assert denied.headers['location'] == '/login/?error=signin_failed'
    replay=client.get('/api/auth/callback/github',params={'code':'replay','state':state},follow_redirects=False)
    assert replay.headers['location'] == '/login/?error=signin_failed'


@pytest.mark.parametrize('fault',[None,'nonce','audience','issuer','expired','signature','email'])
def test_google_oidc_validates_signed_identity(configured_auth, fault):
    key=JsonWebKey.generate_key('RSA',2048,is_private=True,options={'kid':'test-key'})
    other_key=JsonWebKey.generate_key('RSA',2048,is_private=True,options={'kid':'test-key'})
    nonce={}
    def transport(request):
        if request.url.path == '/.well-known/openid-configuration':
            return httpx.Response(200,json={'issuer':'https://accounts.google.com','authorization_endpoint':'https://accounts.google.com/o/oauth2/v2/auth','token_endpoint':'https://oauth2.googleapis.com/token','jwks_uri':'https://www.googleapis.com/oauth2/v3/certs','id_token_signing_alg_values_supported':['RS256']})
        if request.url.path == '/oauth2/v3/certs':return httpx.Response(200,json={'keys':[key.as_dict(is_private=False)]})
        if request.url.path == '/token':
            form=parse_qs(request.content.decode());assert form['code_verifier']
            challenge=base64.urlsafe_b64encode(hashlib.sha256(form['code_verifier'][0].encode()).digest()).rstrip(b'=').decode()
            assert challenge == nonce['challenge']
            now=int(time.time())
            claims={'iss':'https://accounts.google.com','sub':'google-123','aud':'test-google','iat':now,'exp':now+300,'nonce':nonce['value'],'email':'user@example.com','email_verified':True,'name':'Google User'}
            if fault=='nonce':claims['nonce']='wrong'
            if fault=='audience':claims['aud']='wrong'
            if fault=='issuer':claims['iss']='https://attacker.example'
            if fault=='expired':claims['exp']=now-1000
            if fault=='email':claims['email_verified']=False
            encoded=jwt.encode({'alg':'RS256','kid':'test-key'},claims,other_key if fault=='signature' else key).decode()
            return httpx.Response(200,json={'access_token':'google-test-token','token_type':'Bearer','id_token':encoded})
        raise AssertionError(str(request.url))
    remote=configured_auth.oauth.create_client('google');remote.client_kwargs['transport']=httpx.MockTransport(transport)
    client=TestClient(app, base_url="https://127.0.0.1:5173")
    begin=client.get('/api/auth/login/google',follow_redirects=False)
    assert begin.status_code == 302
    q=parse_qs(urlsplit(begin.headers['location']).query)
    nonce.update(value=q['nonce'][0],challenge=q['code_challenge'][0])
    response=client.get('/api/auth/callback/google',params={'code':'test-code','state':q['state'][0]},follow_redirects=False)
    if fault is None:
        assert response.headers['location']=='/dashboard/'
        assert client.get('/api/auth/me').json()['user']['provider']=='google'
    else:
        assert response.headers['location']=='/login/?error=signin_failed'
        assert client.get('/api/auth/me').status_code==401


def test_built_pages_and_authenticated_dashboard(auth_manager, signed_in_client):
    from pathlib import Path
    if not (Path(__file__).resolve().parents[1]/'frontend/dist/index.html').exists():
        pytest.skip('Build the frontend to check production routes')
    public=TestClient(app)
    assert 'Get started' in public.get('/').text
    for path in ['/login/', '/signup/']:
        response=public.get(path)
        assert response.status_code==200
        # The server returns a React shell.
        # Browser tests verify the actual OAuth buttons.
        assert 'id="auth-root"' in response.text
        assert f'data-mode="{path.strip("/")}"' in response.text
        assert '<script ' in response.text
        assert 'Google or GitHub' in response.text
    assert signed_in_client.get('/dashboard/').status_code==200
    assert 'id="root"' in signed_in_client.get('/dashboard/').text
    assert 'id="root"' not in public.get('/dashboard/', follow_redirects=False).text


def test_https_session_cookies_are_secure(configured_auth):
    configured_auth.secure=True
    remote=configured_auth.oauth.create_client('github')
    remote.client_kwargs['transport']=httpx.MockTransport(github_transport)
    client=TestClient(app,base_url='https://testserver')
    start=client.get('/api/auth/login/github',follow_redirects=False)
    state=parse_qs(urlsplit(start.headers['location']).query)['state'][0]
    done=client.get('/api/auth/callback/github',params={'code':'example','state':state},follow_redirects=False)
    assert done.headers['location']=='/dashboard/'
    session_cookie=next(c for c in done.headers.get_list('set-cookie') if c.startswith(COOKIE+'='))
    assert 'Secure' in session_cookie and 'HttpOnly' in session_cookie and 'SameSite=lax' in session_cookie
    assert client.get('/api/auth/me').status_code==200

@pytest.mark.parametrize('destination,expected',[
    ('/join?token='+'a'*43,'/join?token='+'a'*43),
    ('https://attacker.example/','/dashboard/'),
])
def test_oauth_returns_to_invitation_only(configured_auth,destination,expected):
    remote=configured_auth.oauth.create_client('github')
    remote.client_kwargs['transport']=httpx.MockTransport(github_transport)
    client=TestClient(app, base_url="https://127.0.0.1:5173")
    begin=client.get('/api/auth/login/github',params={'next':destination},follow_redirects=False)
    state=parse_qs(urlsplit(begin.headers['location']).query)['state'][0]
    done=client.get('/api/auth/callback/github',params={'code':'example','state':state},follow_redirects=False)
    assert done.headers['location']==expected
