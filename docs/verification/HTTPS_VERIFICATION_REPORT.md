# RepoLens Local HTTPS — Implementation and Verification

## Source

Based on `RepoLens_Sitewide_Charcoal_Blue_Cinematic_Theme_2026-11-13.zip`
(the current whole-website charcoal-and-blue project). The UI, React routes,
RAG, database models and provider logic were not otherwise redesigned.

## Implemented

- `node start.mjs --https` and HTTPS-aware `.env` browser origin; `--http`
  remains an explicit local fallback.
- `node scripts/setup_local_https.mjs` uses mkcert to install a local CA,
  create a SAN certificate for `127.0.0.1`, `localhost`, `::1`, validate its
  private key, restrict file permissions, and update **only** the local `.env`
  browser-origin scheme while preserving private configuration.
- Vite serves HTTPS using local cert and proxies browser `/api` calls to the
  loopback-only FastAPI worker. No browser-side mixed content.
- Vite forwards the validated browser hostname and `X-Forwarded-Proto` to
  Uvicorn. Uvicorn accepts these proxy headers only from `127.0.0.1`, so
  OAuth token exchange sees the same HTTPS callback scheme as authorization.
- FastAPI receives the effective HTTPS `REPOLENS_BASE_URL`; session cookies
  are Secure + HttpOnly + SameSite=Lax via existing auth middleware.
- Certificate/key are excluded from Git, Docker and project ZIP.
- `node scripts/verify_local_https.mjs` verifies the HTTPS site's certificate
  against the mkcert root CA, plus health, OAuth provider API, login and home.
- New Playwright HTTPS browser checks and Mac setup guide.

## Executed in the editing environment

| Approach | Actual result | Limit |
| --- | --- | --- |
| Unit tests | 66/66 frontend Node tests passed | Includes 4 local HTTPS tests and existing suite |
| Other Node regressions | 3/3 GitHub Action tests passed | Unchanged behavior |
| Integration | 1/1 Uvicorn proxy-header test passed | Trusted HTTPS header, untrusted spoof rejected |
| Test-driven regressions | Red import failure before implementing HTTPS, then all new Node tests green | Tests exercise settings and certificate/key validation |
| Setup command harness | Passed using local test certificate | Updated only public URL, preserved mock env secret, private key mode 600 |
| Python OAuth HTTPS security tests | Added, not executed (authlib unavailable; pytest skipped) | Run after `pip install -r requirements.txt` on Mac |
| Full frontend build | Not run successfully (npm ci failed in this container) | Run on Mac |
| Playwright HTTPS E2E | Added, not run (Vite/Playwright dependencies unavailable) | Run on Mac |
| Real Google/GitHub OAuth | Not verified here | Requires OAuth console callback changes and actual provider login |

**No claim of deployed public HTTPS:** this is for trusted localhost development.
The existing Caddy deployment remains the path to public HTTPS with a domain.

## Mac verification

Follow `LOCAL_HTTPS_SETUP.md`, then:

```bash
brew install mkcert
node scripts/setup_local_https.mjs
node start.mjs --https
```

Second Terminal:

```bash
node scripts/verify_local_https.mjs
python -m pytest -q tests/test_local_https_auth.py tests/test_local_https_proxy.py
bash scripts/verify_https.sh
```

Only after these checks and a real OAuth login pass should you consider the
local HTTPS migration accepted on your Mac.
