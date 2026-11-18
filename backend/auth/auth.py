"""Google OIDC / GitHub OAuth with revocable server-side application sessions."""
from __future__ import annotations
from contextlib import contextmanager
import hashlib
import hmac
import ipaddress
import os
import posixpath
from pathlib import Path
import secrets
import sqlite3
import time
from urllib.parse import urlsplit

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Request, Body
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from backend.security.controls import validate_production_settings, audit_route

COOKIE = 'repolens_session'
SESSION_SECONDS = 7 * 24 * 60 * 60
LOGIN_FAILURE_LIMIT = 10
LOGIN_WINDOW_SECONDS = 15 * 60
MAX_ACTIVE_API_KEYS = 10


class CreateApiKey(BaseModel):
    name: str = Field(min_length=1, max_length=200)



class AuthManager:
    def __init__(self, *, directory=None, base_url=None, environ=None):
        env = os.environ if environ is None else environ
        self.base_url = (base_url or env.get('REPOLENS_BASE_URL', 'http://127.0.0.1:5173')).rstrip('/')
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username:
            raise ValueError('REPOLENS_BASE_URL must be an origin, without a path or credentials')
        local = parsed.hostname in ('localhost', '127.0.0.1', '::1')
        production = env.get('REPOLENS_ENV') == 'production'
        if parsed.scheme != 'https' and (production or not local):
            raise ValueError('Use HTTPS for non-local authentication')
        validate_production_settings(env)
        self.secure = parsed.scheme == 'https'
        self.directory = Path(directory or env.get('REPOLENS_AUTH_DIR', Path(__file__).resolve().parents[2] / '.repolens_auth'))
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        secret = env.get('REPOLENS_SESSION_SECRET', '').strip()
        if production and len(secret) < 32:
            raise ValueError('Production requires REPOLENS_SESSION_SECRET of at least 32 characters')
        if secret and len(secret) < 32:
            raise ValueError('REPOLENS_SESSION_SECRET must contain at least 32 characters')
        if not secret:
            secret_path = self.directory / 'secret.key'
            try:
                fd = os.open(secret_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                secret = secret_path.read_text().strip()
            else:
                secret = secrets.token_urlsafe(48)
                with os.fdopen(fd, 'w') as file:
                    file.write(secret)
        if len(secret) < 32:
            raise ValueError('Invalid local session secret; restore the secret file')
        self.session_secret = secret
        self.database = self.directory / 'accounts.sqlite3'
        database_url=env.get('REPOLENS_AUTH_DATABASE_URL')
        self.sql_database=None
        if database_url:
            if not database_url.startswith(('postgresql+psycopg://','sqlite:///')):raise ValueError('Unsupported auth database URL')
            from backend.auth.auth_database import AuthDatabase
            self.sql_database=AuthDatabase(database_url)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, provider TEXT NOT NULL, subject TEXT NOT NULL,
                    name TEXT NOT NULL, email TEXT, created_at INTEGER NOT NULL,
                    UNIQUE(provider, subject)
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                    csrf TEXT NOT NULL, expires_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);
            ''')
        # SQLite local mode remains compatible with existing installations and tests.
        # Hosted PostgreSQL is upgraded with: python -m backend.database.schema_migrations upgrade
        if self.sql_database is None or self.sql_database.engine.dialect.name == 'sqlite':
            with self.connect() as db:
                db.executescript('''
                CREATE TABLE IF NOT EXISTS api_keys (
                    id VARCHAR(32) PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    key_hash VARCHAR(64) NOT NULL UNIQUE,
                    key_prefix VARCHAR(18) NOT NULL,
                    name VARCHAR(200) NOT NULL,
                    created_at INTEGER NOT NULL,
                    last_used_at INTEGER,
                    revoked INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS api_keys_user_idx ON api_keys(user_id);
                CREATE TABLE IF NOT EXISTS session_devices (
                    token_hash TEXT PRIMARY KEY REFERENCES sessions(token_hash) ON DELETE CASCADE,
                    ip_address VARCHAR(45), user_agent VARCHAR(200), created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS login_attempts (
                    ip_address VARCHAR(45) PRIMARY KEY,
                    fail_count INTEGER NOT NULL,
                    window_started INTEGER NOT NULL,
                    locked_until INTEGER
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    id VARCHAR(32) PRIMARY KEY,
                    user_id TEXT,
                    action VARCHAR(64) NOT NULL,
                    target VARCHAR(120),
                    ip_address VARCHAR(45),
                    created_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS audit_events_user_idx ON audit_events(user_id, created_at);
                CREATE TABLE IF NOT EXISTS usage_counters (
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    action VARCHAR(16) NOT NULL, window_start INTEGER NOT NULL,
                    count INTEGER NOT NULL,
                    PRIMARY KEY (user_id, action, window_start)
                );
                CREATE TABLE IF NOT EXISTS request_buckets (
                    identity_hash VARCHAR(64) NOT NULL, action VARCHAR(16) NOT NULL,
                    window_start INTEGER NOT NULL, count INTEGER NOT NULL,
                    PRIMARY KEY (identity_hash, action, window_start)
                );
                CREATE TABLE IF NOT EXISTS usage_events (
                    id VARCHAR(32) PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    action VARCHAR(16) NOT NULL, created_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS usage_events_user_date ON usage_events(user_id, created_at);
                CREATE TABLE IF NOT EXISTS user_plans (
                    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    plan VARCHAR(12) NOT NULL
                );

                ''')
        try:
            self.database.chmod(0o600)
        except OSError:
            pass
        self.oauth = OAuth()
        self.providers = {}
        for provider in ('google', 'github'):
            client_id = env.get(provider.upper() + '_CLIENT_ID', '').strip()
            client_secret = env.get(provider.upper() + '_CLIENT_SECRET', '').strip()
            self.providers[provider] = bool(client_id and client_secret and not client_id.startswith('YOUR_') and not client_secret.startswith('YOUR_'))
            if not self.providers[provider]:
                continue
            common = dict(client_id=client_id, client_secret=client_secret,
                          client_kwargs={'code_challenge_method': 'S256', 'token_endpoint_auth_method': 'client_secret_post', 'timeout': 20.0})
            if provider == 'google':
                common['client_kwargs']['scope'] = 'openid email profile'
                self.oauth.register(provider, server_metadata_url='https://accounts.google.com/.well-known/openid-configuration', **common)
            else:
                common['client_kwargs']['scope'] = 'read:user user:email'
                self.oauth.register(provider, authorize_url='https://github.com/login/oauth/authorize',
                                    access_token_url='https://github.com/login/oauth/access_token',
                                    api_base_url='https://api.github.com/', **common)

    @contextmanager
    def connect(self):
        if self.sql_database is not None:
            with self.sql_database.connect() as db:yield db
            return
        db = sqlite3.connect(self.database, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def upsert_user(self, provider, subject, name, email=None):
        if provider not in ('google', 'github') or not str(subject).strip():
            raise ValueError('Invalid provider identity')
        # Never merge accounts by email: provider + immutable subject owns the account.
        with self.connect() as db:
            db.execute('''INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider, subject) DO UPDATE SET name=excluded.name, email=excluded.email''',
                (secrets.token_hex(16), provider, str(subject), str(name)[:200], email, int(time.time())))
            return dict(db.execute('SELECT id, provider, name, email FROM users WHERE provider=? AND subject=?', (provider, str(subject))).fetchone())

    def new_session(self, user_id, *, ip_address=None, user_agent=None):
        token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
        now = int(time.time())
        token_hash = self.token_hash(token)
        with self.connect() as db:
            db.execute('DELETE FROM session_devices WHERE token_hash IN (SELECT token_hash FROM sessions WHERE expires_at <= ?)', (now,))
            db.execute('DELETE FROM sessions WHERE expires_at <= ?', (now,))
            db.execute('INSERT INTO sessions (token_hash, user_id, csrf, expires_at) VALUES (?, ?, ?, ?)',
                       (token_hash, user_id, csrf, now + SESSION_SECONDS))
            db.execute('INSERT INTO session_devices (token_hash, ip_address, user_agent, created_at) VALUES (?, ?, ?, ?)',
                       (token_hash, (ip_address or '')[:45] or None, (user_agent or '')[:200] or None, now))
        return token

    @staticmethod
    def token_hash(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def authenticate(self, token):
        if not token or len(token) > 200:
            return None
        with self.connect() as db:
            row = db.execute('''SELECT u.id, u.provider, u.name, u.email, s.csrf
                FROM sessions s JOIN users u ON u.id=s.user_id
                WHERE s.token_hash=? AND s.expires_at>?''', (self.token_hash(token), int(time.time()))).fetchone()
        return dict(row) if row else None

    def revoke(self, token):
        if token:
            digest = self.token_hash(token)
            with self.connect() as db:
                db.execute('DELETE FROM session_devices WHERE token_hash=?', (digest,))
                db.execute('DELETE FROM sessions WHERE token_hash=?', (digest,))

    def list_sessions(self, user_id, current_token):
        now = int(time.time())
        current_hash = self.token_hash(current_token or '')
        with self.connect() as db:
            rows = db.execute('''SELECT s.token_hash, s.expires_at,
                       d.ip_address, d.user_agent, d.created_at
                       FROM sessions s LEFT JOIN session_devices d ON d.token_hash=s.token_hash
                       WHERE s.user_id=? AND s.expires_at>?
                       ORDER BY s.expires_at DESC, s.token_hash''', (user_id, now)).fetchall()
        return [{'id': row['token_hash'][:12], 'current': row['token_hash'] == current_hash,
                 'expires_at': row['expires_at'], 'created_at': row['created_at'],
                 'ip_address': row['ip_address'], 'user_agent': row['user_agent']}
                for row in rows]

    def revoke_all_sessions(self, user_id):
        with self.connect() as db:
            db.execute('DELETE FROM session_devices WHERE token_hash IN (SELECT token_hash FROM sessions WHERE user_id=?)', (user_id,))
            db.execute('DELETE FROM sessions WHERE user_id=?', (user_id,))
            self.record_audit('auth:all_sessions_revoked', user_id=user_id, connection=db)

    def record_audit(self, action, *, user_id=None, target=None, ip_address=None, connection=None):
        # Audit only structured, allowlisted identifiers. Never store request
        # bodies, OAuth claims, API tokens, provider errors or query strings.
        import re
        if not re.fullmatch(r'[a-z][a-z0-9_]*:[a-z][a-z0-9_]*', action):
            raise ValueError('Invalid audit event type')
        if target is not None and not re.fullmatch(r'[A-Za-z0-9_-]{1,120}', str(target)):
            target = None
        if ip_address:
            try:
                ip_address = str(ipaddress.ip_address(ip_address))
            except ValueError:
                ip_address = None
        def write(db):
            db.execute('''INSERT INTO audit_events
                      (id,user_id,action,target,ip_address,created_at)
                      VALUES (?,?,?,?,?,?)''',
                       (secrets.token_hex(16),user_id,action,target,ip_address,int(time.time())))
        if connection is not None:
            write(connection)
        else:
            with self.connect() as db:
                write(db)

    def recent_audit(self, user_id, *, limit=20):
        with self.connect() as db:
            rows = db.execute('''SELECT id,action,target,created_at FROM audit_events
                       WHERE user_id=? ORDER BY created_at DESC, id DESC LIMIT ?''',
                       (user_id, max(1,min(int(limit),50)))).fetchall()
        return [dict(row) for row in rows]

    def create_api_key(self, user_id, name):
        name = str(name).strip()
        if not 1 <= len(name) <= 200:
            raise ValueError('Key name must be 1-200 characters')
        raw = 'rl_live_' + secrets.token_urlsafe(32)
        key_id = secrets.token_hex(16)
        now = int(time.time())
        with self.connect() as db:
            # Serialize key creation for this user on PostgreSQL; two simultaneous
            # requests must not both pass the active-key count check.
            if self.sql_database is not None and self.sql_database.engine.dialect.name == 'postgresql':
                db.execute('SELECT id FROM users WHERE id=? FOR UPDATE', (user_id,))
            total = db.execute('SELECT COUNT(*) AS total FROM api_keys WHERE user_id=? AND revoked=0', (user_id,)).fetchone()['total']
            if total >= MAX_ACTIVE_API_KEYS:
                raise ValueError('Revoke an unused key before creating another (10 active keys maximum).')
            db.execute('''INSERT INTO api_keys
                         (id, user_id, key_hash, key_prefix, name, created_at, revoked)
                         VALUES (?, ?, ?, ?, ?, ?, 0)''',
                       (key_id, user_id, self.token_hash(raw), raw[:16], name, now))
            self.record_audit('api_key:created', user_id=user_id, target=key_id, connection=db)
        return {'id': key_id, 'key': raw, 'name': name, 'created_at': now}

    def list_api_keys(self, user_id):
        with self.connect() as db:
            rows = db.execute('''SELECT id, key_prefix, name, created_at, last_used_at
                       FROM api_keys WHERE user_id=? AND revoked=0
                       ORDER BY created_at DESC, id''', (user_id,)).fetchall()
        return [dict(row) for row in rows]

    def revoke_api_key(self, user_id, key_id):
        with self.connect() as db:
            result = db.execute('UPDATE api_keys SET revoked=1 WHERE id=? AND user_id=? AND revoked=0', (key_id, user_id))
            if result.rowcount:
                self.record_audit('api_key:revoked', user_id=user_id, target=key_id, connection=db)
        return result.rowcount > 0

    def authenticate_api_key(self, raw):
        if not isinstance(raw, str) or not raw.startswith('rl_live_') or len(raw) > 200:
            return None
        now = int(time.time())
        with self.connect() as db:
            row = db.execute('''SELECT u.id, u.provider, u.name, u.email, k.id AS key_id
                       FROM api_keys k JOIN users u ON k.user_id=u.id
                       WHERE k.key_hash=? AND k.revoked=0''', (self.token_hash(raw),)).fetchone()
            if row:
                db.execute('UPDATE api_keys SET last_used_at=? WHERE id=?', (now, row['key_id']))
        return {k: row[k] for k in ('id', 'provider', 'name', 'email')} if row else None

    def login_locked(self, ip_address):
        if not ip_address:
            return False
        with self.connect() as db:
            row = db.execute('SELECT locked_until FROM login_attempts WHERE ip_address=?', (ip_address[:45],)).fetchone()
        return bool(row and row['locked_until'] and row['locked_until'] > int(time.time()))

    def record_login_failure(self, ip_address):
        if not ip_address:
            return
        ip_address = ip_address[:45]
        now = int(time.time())
        with self.connect() as db:
            row = db.execute('SELECT fail_count, window_started, locked_until FROM login_attempts WHERE ip_address=?', (ip_address,)).fetchone()
            if row and row['locked_until'] and row['locked_until'] > now:
                return
            fail_count = 1 if not row or row['window_started'] < now - LOGIN_WINDOW_SECONDS else row['fail_count'] + 1
            started = now if fail_count == 1 else row['window_started']
            locked_until = now + LOGIN_WINDOW_SECONDS if fail_count >= LOGIN_FAILURE_LIMIT else None
            if row:
                db.execute('UPDATE login_attempts SET fail_count=?, window_started=?, locked_until=? WHERE ip_address=?',
                           (fail_count, started, locked_until, ip_address))
            else:
                db.execute('INSERT INTO login_attempts (ip_address,fail_count,window_started,locked_until) VALUES (?,?,?,?)',
                           (ip_address, fail_count, started, locked_until))
            self.record_audit('auth:login_failure', ip_address=ip_address, connection=db)

    def record_login_success(self, ip_address, user_id=None):
        with self.connect() as db:
            if ip_address:
                db.execute('DELETE FROM login_attempts WHERE ip_address=?', (ip_address[:45],))
            self.record_audit('auth:login_success', user_id=user_id, ip_address=ip_address, connection=db)

    def usage_snapshot(self, user_id, *, now=None, limits=None):
        """Per-user UTC usage and limits; no tokens, IPs, or keys are returned."""
        from backend.security.usage_limits import PLAN_LIMITS
        now=int(time.time() if now is None else now)
        limits=PLAN_LIMITS if limits is None else limits
        utc_day=(now//86400)*86400
        with self.connect() as db:
            row=db.execute('SELECT plan FROM user_plans WHERE user_id=?',(user_id,)).fetchone()
            plan=row['plan'] if row and row['plan'] in limits else 'free'
            values={}
            for action,limit in limits[plan].items():
                found=db.execute('SELECT count FROM usage_counters WHERE user_id=? AND action=? AND window_start=?',
                                 (user_id,action,utc_day)).fetchone()
                used=int(found['count']) if found else 0
                values[action]={'used':used,'limit':limit,'remaining':max(0,limit-used)}
        return {'plan':plan,'usage':values,'reset_at':utc_day+86400}

    def reserve_usage(self, user_id, action, ip_address, *, now=None, limits=None, hourly=None):
        """Atomically reserve hourly IP AND daily user capacity, or reserve neither."""
        from fastapi import HTTPException
        from backend.security.usage_limits import PLAN_LIMITS, HOURLY_LIMITS
        limits=PLAN_LIMITS if limits is None else limits
        hourly=HOURLY_LIMITS if hourly is None else hourly
        now=int(time.time() if now is None else now)
        day=(now//86400)*86400
        hour=(now//3600)*3600
        with self.connect() as db:
            plan_row=db.execute('SELECT plan FROM user_plans WHERE user_id=?',(user_id,)).fetchone()
            plan=plan_row['plan'] if plan_row and plan_row['plan'] in limits else 'free'
            if action not in limits[plan] or action not in hourly:
                raise ValueError('Unknown usage action')
            # HMAC protects raw IP addresses at rest. Shared IPs share an
            # hourly request bucket; accounts have separate daily budgets.
            raw_ip=(ip_address or 'unknown')[:45]
            ip_key=hmac.new(self.session_secret.encode(),raw_ip.encode(),'sha256').hexdigest()
            per_hour=int(hourly[action]); per_day=int(limits[plan][action])
            # Single transaction: when either upsert fails the context manager
            # rolls back the other reservation as well.
            ip_row=db.execute('''INSERT INTO request_buckets(identity_hash,action,window_start,count)
                VALUES(?,?,?,1) ON CONFLICT(identity_hash,action,window_start)
                DO UPDATE SET count=request_buckets.count+1
                WHERE request_buckets.count < ? RETURNING count''',
                (ip_key,action,hour,per_hour)).fetchone() if per_hour>0 else None
            if not ip_row:
                raise HTTPException(429,'Hourly request limit reached. Try again later.',
                                    headers={'Retry-After':str(max(1,hour+3600-now))})
            user_row=db.execute('''INSERT INTO usage_counters(user_id,action,window_start,count)
                VALUES(?,?,?,1) ON CONFLICT(user_id,action,window_start)
                DO UPDATE SET count=usage_counters.count+1
                WHERE usage_counters.count < ? RETURNING count''',
                (user_id,action,day,per_day)).fetchone() if per_day>0 else None
            if not user_row:
                raise HTTPException(429,'Daily AI usage limit reached. Your allowance resets at 00:00 UTC.',
                                    headers={'Retry-After':str(max(1,day+86400-now))})
            db.execute('INSERT INTO usage_events(id,user_id,action,created_at) VALUES(?,?,?,?)',
                       (secrets.token_hex(16),user_id,action,now))
            used=int(user_row['count'])
        return {'plan':plan,'action':action,'used':used,'limit':per_day,'remaining':max(0,per_day-used),
                'reset_at':day+86400}

    def check_csrf(self, request, user):
        supplied = request.headers.get('x-csrf-token', '')
        origin = request.headers.get('origin')
        if not supplied or not hmac.compare_digest(supplied, user['csrf']) or (origin is not None and origin != self.base_url):
            raise HTTPException(403, 'Invalid request token. Refresh the page and try again.')


def install_auth(app):
    manager = AuthManager()
    app.state.auth = manager
    app.add_middleware(SessionMiddleware, secret_key=manager.session_secret,
                       session_cookie='repolens_oauth', max_age=600, same_site='lax', https_only=manager.secure)
    if os.getenv('REPOLENS_ENV') == 'production':
        # Keep strict host validation for both the public Vercel site and
        # the original Render hostname used by the Vercel API proxy.
        public_host = urlsplit(manager.base_url).hostname
        allowed_hosts = [public_host]
        render_host = os.getenv('RENDER_EXTERNAL_HOSTNAME', '').strip().lower()
        if render_host.endswith('.onrender.com') and render_host not in allowed_hosts:
            allowed_hosts.append(render_host)
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts, www_redirect=False)

    def login_client_ip(request):
        # Do not trust client-supplied X-Forwarded-For unless the immediate
        # network peer is a configured reverse proxy. Uvicorn may also set
        # request.client.host itself when its proxy headers are configured.
        peer = request.client.host if request.client else ''
        trusted = os.getenv('REPOLENS_TRUSTED_PROXY_NETWORKS', '')
        try:
            parsed_peer = ipaddress.ip_address(peer)
            for network_text in trusted.split(','):
                network_text = network_text.strip()
                if not network_text:
                    continue
                if parsed_peer in ipaddress.ip_network(network_text, strict=False):
                    forwarded = request.headers.get('x-forwarded-for', '')
                    candidate = forwarded.split(',')[-1].strip()
                    try:
                        return str(ipaddress.ip_address(candidate))
                    except ValueError:
                        break
        except ValueError:
            pass
        return peer[:45]

    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; connect-src 'self'; "
            "form-action 'self'; frame-ancestors 'none'; base-uri 'self'; object-src 'none'"
        )
        response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
        response.headers['X-Permitted-Cross-Domain-Policies'] = 'none' 
        if os.getenv('REPOLENS_ENV') == 'production' and manager.secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    @app.middleware('http')
    async def protect_workspace(request, call_next):
        path = posixpath.normpath('/' + request.scope['path'].lstrip('/'))
        is_api = path.startswith('/api/')
        public_checklist = path.startswith('/api/public/checklists/')
        protected = (is_api and path != '/api/health' and not path.startswith('/api/auth/') and not public_checklist) or path in ('/docs', '/redoc', '/openapi.json') or path == '/dashboard' or path.startswith('/dashboard/')
        if protected:
            auth = request.app.state.auth
            bearer = request.headers.get('authorization', '') if is_api else ''
            # Bearer authentication is only permitted for application APIs,
            # never for account/session management or browser dashboard pages.
            if bearer:
                if not bearer.startswith('Bearer '):
                    user = None
                else:
                    user = auth.authenticate_api_key(bearer[7:].strip())
                using_bearer = True
            else:
                user = auth.authenticate(request.cookies.get(COOKIE))
                using_bearer = False
            if not user:
                response = JSONResponse({'detail': 'Sign in to continue.'}, status_code=401) if is_api else RedirectResponse('/login/', status_code=303)
                response.headers['Cache-Control'] = 'no-store'
                return security_headers(response)
            request.state.user = user
            if not using_bearer and request.method not in ('GET', 'HEAD', 'OPTIONS'):
                try:
                    auth.check_csrf(request, user)
                except HTTPException as exc:
                    return security_headers(JSONResponse({'detail': exc.detail}, status_code=exc.status_code, headers={'Cache-Control': 'no-store'}))
        # Charge costly operations after authentication/CSRF but before
        # Gemini/GitHub. Malformed attempts count against request allowance.
        quota_result = None
        if protected and getattr(request.state,'user',None):
            from backend.security.usage_limits import action_for_request
            action = action_for_request(request.method,path)
            if action:
                try:
                    from fastapi.concurrency import run_in_threadpool
                    quota_result = await run_in_threadpool(
                        request.app.state.auth.reserve_usage,
                        request.state.user['id'], action, login_client_ip(request))
                except HTTPException as error:
                    headers={'Cache-Control':'no-store','Vary':'Cookie',**(error.headers or {})}
                    return security_headers(JSONResponse({'detail':error.detail},
                                              status_code=error.status_code,headers=headers))
                except Exception as error:
                    # Fail closed: never allow a costly model request when
                    # quota storage is missing or temporarily unavailable.
                    import logging
                    logging.getLogger(__name__).error('Usage reservation unavailable (%s)', type(error).__name__)
                    return security_headers(JSONResponse(
                        {'detail':'AI usage protection is temporarily unavailable. Try again after the database is checked.'},
                        status_code=503,headers={'Cache-Control':'no-store'}))
        response = await call_next(request)
        if quota_result:
            response.headers['X-RateLimit-Limit'] = str(quota_result['limit'])
            response.headers['X-RateLimit-Remaining'] = str(quota_result['remaining'])

        # Only successful, authenticated, allowlisted mutation routes are audited.
        # The log contains a whitelisted action and opaque ID, never the URL,
        # query string, payload, invite token or response body.
        matched = audit_route(request.method, path) if 200 <= response.status_code < 400 else None
        if matched and getattr(request.state, 'user', None):
            action, target = matched
            request.app.state.auth.record_audit(action, user_id=request.state.user['id'], target=target)
        if protected or path.startswith('/api/auth/') or public_checklist:
            response.headers['Cache-Control'] = 'no-store'
            response.headers['Vary'] = 'Cookie'
        return security_headers(response)

    def cookie_user(request: Request, *, mutation=False):
        # API tokens cannot create other API tokens or revoke browser sessions.
        if request.headers.get('authorization'):
            raise HTTPException(401, 'Use your signed-in browser session for account security settings.')
        auth = request.app.state.auth
        user = auth.authenticate(request.cookies.get(COOKIE))
        if not user:
            raise HTTPException(401, 'Sign in to continue.')
        if mutation:
            auth.check_csrf(request, user)
        return user

    router = APIRouter(prefix='/api/auth')

    @router.get('/providers')
    async def providers(request: Request):
        return {'providers': request.app.state.auth.providers}

    @router.get('/me')
    async def me(request: Request):
        user = request.app.state.auth.authenticate(request.cookies.get(COOKIE))
        if not user:
            raise HTTPException(401, 'Sign in to continue.')
        return {'user': {k: v for k, v in user.items() if k != 'csrf'}, 'csrf_token': user['csrf']}

    @router.get('/keys')
    async def list_keys(request: Request):
        user = cookie_user(request)
        return {'keys': request.app.state.auth.list_api_keys(user['id'])}

    @router.post('/keys', status_code=201)
    async def create_key(request: Request, body: CreateApiKey):
        user = cookie_user(request, mutation=True)
        try:
            return request.app.state.auth.create_api_key(user['id'], body.name)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None

    @router.delete('/keys/{key_id}')
    async def revoke_key(request: Request, key_id: str):
        user = cookie_user(request, mutation=True)
        if not request.app.state.auth.revoke_api_key(user['id'], key_id):
            raise HTTPException(404, 'API key not found.')
        return {'revoked': True}

    @router.get('/audit')
    async def audit_log(request: Request):
        user = cookie_user(request)
        return {'events': request.app.state.auth.recent_audit(user['id'])}

    @router.get('/sessions')
    async def sessions(request: Request):
        user = cookie_user(request)
        return {'sessions': request.app.state.auth.list_sessions(user['id'], request.cookies.get(COOKIE))}

    @router.delete('/sessions/all')
    async def revoke_all(request: Request):
        user = cookie_user(request, mutation=True)
        auth = request.app.state.auth
        auth.revoke_all_sessions(user['id'])
        request.session.clear()
        response = JSONResponse({'revoked': True})
        response.delete_cookie(COOKIE, path='/', httponly=True, secure=auth.secure, samesite='lax')
        return response

    @router.get('/login/{provider}')
    async def begin(request: Request, provider: str):
        auth = request.app.state.auth
        if provider not in auth.providers:
            raise HTTPException(404, 'Unknown sign-in provider')
        if not auth.providers[provider]:
            return RedirectResponse('/login/?error=provider_unavailable', status_code=303)
        if auth.login_locked(login_client_ip(request)):
            return RedirectResponse('/login/?error=too_many_attempts', status_code=303)
        request.session.clear()
        next_path=request.query_params.get('next','')
        import re
        if re.fullmatch(r'/join\?token=[A-Za-z0-9_-]{20,200}',next_path):
            request.session['return_to']=next_path
        try:
            return await auth.oauth.create_client(provider).authorize_redirect(
                request, f'{auth.base_url}/api/auth/callback/{provider}', prompt='select_account')
        except Exception:
            request.session.clear()
            return RedirectResponse('/login/?error=provider_unavailable', status_code=303)

    @router.get('/callback/{provider}')
    async def callback(request: Request, provider: str):
        auth = request.app.state.auth
        if provider not in auth.providers or not auth.providers[provider]:
            return RedirectResponse('/login/?error=provider_unavailable', status_code=303)
        login_ip = login_client_ip(request)
        if auth.login_locked(login_ip):
            return RedirectResponse('/login/?error=too_many_attempts', status_code=303)
        try:
            client = auth.oauth.create_client(provider)
            # Authlib checks OAuth state; Google OIDC additionally verifies the ID
            # token signature, issuer, audience, expiration, and nonce.
            token = await client.authorize_access_token(request)
            if provider == 'google':
                info = token.get('userinfo')
                if not token.get('id_token') or not info or not info.get('sub') or info.get('email_verified') is not True:
                    raise ValueError('Unverified Google identity')
                user = auth.upsert_user(provider, info['sub'], info.get('name') or 'Google user', info.get('email'))
            else:
                response = await client.get('user', token=token)
                response.raise_for_status()
                info = response.json()
                if not isinstance(info.get('id'), int) or info['id'] <= 0:
                    raise ValueError('Missing GitHub identity')
                response = await client.get('user/emails', token=token)
                response.raise_for_status()
                emails = response.json()
                verified = [e for e in emails if e.get('verified') is True]
                primary = next((e for e in verified if e.get('primary')), verified[0] if verified else {})
                user = auth.upsert_user(provider, str(info['id']), info.get('name') or info.get('login') or 'GitHub user', primary.get('email'))
            auth.revoke(request.cookies.get(COOKIE))
            session = auth.new_session(user['id'], ip_address=login_ip,
                                       user_agent=request.headers.get('user-agent', ''))
            auth.record_login_success(login_ip, user_id=user['id'])
        except Exception:
            auth.record_login_failure(login_ip)
            request.session.clear()
            return RedirectResponse('/login/?error=signin_failed', status_code=303)
        return_to=request.session.get('return_to','/dashboard/')
        request.session.clear()
        response = RedirectResponse(return_to, status_code=303)
        response.set_cookie(COOKIE, session, max_age=SESSION_SECONDS, httponly=True, secure=auth.secure, samesite='lax', path='/')
        return response

    @router.post('/logout')
    async def logout(request: Request):
        auth = request.app.state.auth
        user = auth.authenticate(request.cookies.get(COOKIE))
        if not user:
            raise HTTPException(401, 'Sign in to continue.')
        auth.check_csrf(request, user)
        auth.revoke(request.cookies.get(COOKIE))
        auth.record_audit('auth:logout', user_id=user['id'])
        request.session.clear()
        response = JSONResponse({'ok': True})
        response.delete_cookie(COOKIE, path='/', httponly=True, secure=auth.secure, samesite='lax')
        return response

    app.include_router(router)
