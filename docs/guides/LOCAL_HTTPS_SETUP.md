# RepoLens — trusted local HTTPS (macOS)

This project has been updated to serve the **browser-facing website at HTTPS** with
one local command. The public landing page, login/sign-up pages, dashboard,
Knowledge Hub, gallery, and browser `/api` requests use the same HTTPS origin.
Vite terminates TLS with a **locally trusted mkcert certificate**. The FastAPI
process remains on **HTTP bound only to 127.0.0.1** behind the Vite proxy. There
is no mixed-content browser request. This is a normal loopback reverse-proxy
architecture, **not** a public production deployment.

## 1. From zero in the extracted project

Open the folder containing `start.mjs` and `requirements.txt` in VS Code, then:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cd frontend
npm ci
npx playwright install chromium
cd ..
```

Copy the private `.env` from your previous working RepoLens project into this
**new** project root. Keep all existing Gemini, GitHub, Google, PostgreSQL,
Neon, and other secrets private. Never paste them into chat, logs or Git.

## 2. Install mkcert once on your Mac and create local certificates

```bash
brew install mkcert
node scripts/setup_local_https.mjs
```

`setup_local_https.mjs` runs `mkcert -install`. macOS may ask for your account
password **to trust the local development certificate authority**. That's an
operating-system authorization step, not a RepoLens password. Use Homebrew's
legitimate mkcert installation. The script creates `.certs/localhost.pem` and
`.certs/localhost-key.pem`, checks their validity, and changes only the
`REPOLENS_BASE_URL` entry in your private `.env` to HTTPS. Certificate private
keys and your `.env` are gitignored, excluded from Docker and never shipped in
the project ZIP.

If `.env` does not exist yet, copy it from your working project and set:

```dotenv
REPOLENS_BASE_URL=https://127.0.0.1:5173
REPOLENS_ENV=development
```

`REPOLENS_ENV=production` is **not** appropriate for a local mkcert setup.

## 3. Register the new HTTPS OAuth callback URLs

These changes happen in your existing provider consoles, **not** in this ZIP:

- Google OAuth client → authorized redirect URI:
  `https://127.0.0.1:5173/api/auth/callback/google`
- GitHub OAuth app → authorization callback URL:
  `https://127.0.0.1:5173/api/auth/callback/github`

Set the corresponding application homepage/origin to
`https://127.0.0.1:5173` where the provider offers that setting. The exact
scheme, hostname and port must match `REPOLENS_BASE_URL`. If a provider does
not permit the loopback IP address in its console, use `localhost` consistently
in **both** `REPOLENS_BASE_URL` and provider settings, and ensure Vite is
reachable on that hostname; do not mix hosts in a login attempt.

Google and GitHub may require you to register an additional OAuth app/client
when the current one is configured for HTTP only. Keep client secrets unchanged
unless the provider requires replacement. Until the callback URLs are updated,
HTTPS page load may work while **OAuth sign-in fails**.

## 4. Start RepoLens (one command)

```bash
node start.mjs --https
```

Open **https://127.0.0.1:5173/** and then
**https://127.0.0.1:5173/dashboard/**. A browser padlock/connection-details
view should show a valid certificate issued by your local mkcert authority.
Never click through a certificate warning; repair the local trust setup instead.

### If port 8000 is occupied

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
```

Stop **only** the old RepoLens process in its own terminal with `Ctrl+C` or,
after verifying the owning PID, use:

```bash
node start.mjs --https --backend-port 8001
```

The browser continues to use HTTPS on port 5173 and the launcher automatically
updates Vite's internal API proxy to the new loopback backend port.

## 5. Verify actual TLS, API, login and browser E2E

In a **second** terminal while RepoLens is running:

```bash
cd /path/to/your/new/RepoLens
node scripts/verify_local_https.mjs
curl --fail --cacert "$(mkcert -CAROOT)/rootCA.pem" \
  https://127.0.0.1:5173/api/health
```

The verification checks HTTPS certificate chain and hostname against the
mkcert root CA, not an insecure TLS bypass; `/`, `/login/`, `/api/health` and
`/api/auth/providers` are checked over the HTTPS website origin.

Then use:

```bash
bash scripts/verify_https.sh
```

That runs unit, frontend regression/TDD, production build and focused HTTPS
Playwright E2E. To run the E2E cases alone:

```bash
cd frontend
npx playwright test --config=playwright.https.config.js
```

Full **live** Google/GitHub sign-in must be tested manually with your configured
OAuth applications. A mocked auth test is not proof of a working provider.

## 6. Technical notes and troubleshooting

- All **browser** API requests are relative `/api/...`, so they inherit HTTPS
  automatically. The internal FastAPI health probe and Vite→FastAPI proxy stay
  on `http://127.0.0.1:8000`, protected by loopback binding and not accessible
  remotely.
- The Vite proxy forwards the validated public hostname and `X-Forwarded-Proto`
  to Uvicorn, which trusts proxy headers only from loopback. This preserves
  HTTPS OAuth callback URLs during authorization **and token exchange**.
- HTTPS sessions use `Secure`, `HttpOnly`, `SameSite=Lax` cookies. The effective
  `REPOLENS_BASE_URL` is passed to the backend process even if an older private
  `.env` still contains HTTP.
- The certificate includes `127.0.0.1`, `localhost`, and `::1`. Access the
  hostname configured in your OAuth console, consistently. Re-run the setup if
  certificates expire.
- **Do not** run `npm run dev` by itself for HTTPS: use `node start.mjs --https`
  so both processes and the OAuth origin are configured together.
- Port 5173 must be free. The launcher never automatically kills other processes.
- `node start.mjs --http` explicitly restores local HTTP for troubleshooting,
  but an existing HTTPS login session cookie will not be sent over HTTP; log in
  again after switching schemes.
- macOS mkcert creates a **development-only** trusted CA. Do not use these keys
  on a public server. For deployment, the existing `deployment/Caddyfile` uses
  public domain HTTPS with ACME/Let's Encrypt. A domain/DNS and production
  configuration are still needed before deploying online.

