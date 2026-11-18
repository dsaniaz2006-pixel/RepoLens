# Enable real Google and GitHub sign-in

## What is implemented, and what still needs your account settings

Google OpenID Connect and GitHub OAuth are implemented in `auth.py`. Both signup and login use provider authorization. A successful first sign-in creates an account; subsequent sign-ins with the same provider identity reuse it. Accounts are not merged by email. Use the same provider to return to your existing reports.

The delivered ZIP deliberately has no OAuth client secrets. No live Google/GitHub consent flow was completed during development because your OAuth registrations and credentials were not available. Offline tests exercise real Authlib state/PKCE/OIDC validation against simulated provider HTTP responses, including signed Google ID tokens. They are not evidence of live provider activation.

The existing `chatgpt.site` publication is a static frontend. Publishing that frontend does not deploy Python, SQLite, or OAuth callbacks. To enable live login, deploy this complete FastAPI project on a Python-capable host with HTTPS and persistent storage. Serve the frontend and `/api` from the SAME origin. Do not point OAuth callbacks at a static-only site.

## 1. Install the added authentication dependencies

From the extracted `RepoLens` folder on macOS:

```bash
.venv/bin/python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
```

If this is a fresh folder without `.venv`, create it once with `python3 -m venv .venv` first. On Windows use `.venv\Scripts\python.exe` instead.

Create `.env` from `.env.example` only if you do not already have one; preserve your existing Gemini key. Enter secrets in this local file or your hosting provider's secret settings, never in frontend JavaScript or a chat message.

## 2. Register Google

1. In Google Cloud / Google Auth Platform, create or select a project. Configure the app's branding, audience, support email, and consent screen.
2. Create an OAuth client of type **Web application**.
3. Add this exact authorized redirect URI for local development:

   `http://127.0.0.1:5173/api/auth/callback/google`

4. If the consent app is in testing mode, add the Google accounts that will test it as test users. Complete the provider's publication/verification requirements before general public use.
5. Put its client ID and client secret in `.env` as `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.

This server-side flow uses the redirect URI; a browser JavaScript Google SDK is not used. The requested scopes are `openid email profile`.

Official reference: https://developers.google.com/identity/openid-connect/openid-connect

## 3. Register GitHub

1. Open GitHub Settings → Developer settings → OAuth Apps → New OAuth App.
2. Set the homepage URL to `http://127.0.0.1:5173`.
3. Set **Authorization callback URL** to:

   `http://127.0.0.1:5173/api/auth/callback/github`

4. Generate a client secret. Put the values in `.env` as `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET`.

A GitHub personal access token (`GITHUB_TOKEN`) is a different credential and cannot substitute for these OAuth values. This flow requests only `read:user user:email`, not repository write permissions. Use separate GitHub OAuth apps for local and production callback URLs.

Official reference: https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps

## 4. Start locally

Use these settings:

```dotenv
REPOLENS_BASE_URL=http://127.0.0.1:5173
REPOLENS_ENV=development
GOOGLE_CLIENT_ID=<your Google web client ID>
GOOGLE_CLIENT_SECRET=<your Google client secret>
GITHUB_CLIENT_ID=<your GitHub OAuth app client ID>
GITHUB_CLIENT_SECRET=<your GitHub client secret>
```

Check presence and callback addresses without displaying secrets:

```bash
.venv/bin/python scripts/check_auth.py
node start.mjs
```

Open `http://127.0.0.1:5173/`. Use **Get started**, choose a provider, approve on the provider's website, and return to `/dashboard/`. Do not switch between `localhost` and `127.0.0.1`; cookies and callback URLs are tied to the host. Vite must stay on port 5173; startup now uses `--strictPort` to avoid silently changing the callback address.

The buttons enable only when the backend reports that the corresponding client ID and secret are configured. Configuration presence does not prove those credentials are valid. Invalid provider settings or denied consent return a clear login error without granting access.

## 5. Deploy the complete app

A Dockerfile is included for a host with container support. It builds the frontend and serves it from FastAPI. Set these runtime variables through your host's secret/environment settings:

- `REPOLENS_ENV=production`
- `REPOLENS_BASE_URL=https://YOUR-ACTUAL-DOMAIN` (origin only, no trailing path)
- `REPOLENS_SESSION_SECRET`: generate with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`; keep it stable and private.
- All four OAuth client values above.
- `GEMINI_API_KEY`, and optionally `GITHUB_TOKEN`, for repository features.

Add the two production callbacks in the respective provider settings, using your actual domain:

- `https://YOUR-ACTUAL-DOMAIN/api/auth/callback/google`
- `https://YOUR-ACTUAL-DOMAIN/api/auth/callback/github`

Mount persistent storage at `/data` for the supplied Docker configuration. It holds accounts, sessions, reports, and the public-source Chroma cache. Start with one application instance on one persistent volume; SQLite is not a shared database for independent container replicas. Do not expose the storage directory as static files. The Dockerfile is provided but was not built or deployed in this environment.

For a non-Docker Python host, build `frontend/dist` first and start `uvicorn backend.api.api:app --host 0.0.0.0 --port 8000 --no-access-log`, adapting the port to the host. Configure persistent `REPOLENS_AUTH_DIR` and `REPOLENS_REPORT_DIR`, and preserve `.repolens_chroma` or set `REPOLENS_CHROMA_PATH`. HTTPS must terminate at your trusted host/proxy. Keep `/api` same-origin; no permissive CORS is added.

## Live acceptance checks after adding credentials

1. New Google user → signup → Google consent → workspace; reload and confirm session persists.
2. Sign out; open `/dashboard/` directly and verify it redirects to login. `/api/history` must return 401.
3. Returning Google user → login → same account and own history.
4. Repeat with a GitHub account. Google/GitHub accounts remain distinct unless a future explicit linking feature is added.
5. Cancel provider consent and confirm no workspace session is issued.
6. Verify users cannot access one another's history or Markdown/PDF downloads.

## Security behavior

- Authlib validates OAuth state and PKCE for both providers; Google ID tokens are validated for signature, issuer, audience, expiry, and nonce. Only verified Google email claims are accepted.
- Application sessions use random opaque tokens in HttpOnly, SameSite=Lax cookies. HTTPS deployments set Secure. Only a token hash is stored in SQLite. Sessions expire after seven days and are revoked on sign-out.
- Provider access tokens are used during the callback and are not stored in the application database or sent to frontend JavaScript.
- Protected API mutations and logout require the server-issued CSRF token; foreign Origin headers are rejected.
- The React workspace mounts only after `/api/auth/me` succeeds. FastAPI also rejects unauthenticated API requests and protects dashboard HTML when serving the build.
- New web reports are isolated by account under `reports/users/<opaque-user-id>/`. Existing CLI reports remain on disk and are not automatically assigned to a new account. Public example reports remain public.
