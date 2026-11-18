# Phase 11 — Setup, HTTPS, maintenance, backup, recovery

**Release candidate:** `1.1.0-rc.1` • **Status:** NOT FULLY VERIFIED until the live gates pass. Keep the existing RepoLens theme/UI. Do not replace your working `.env` or your database.

## Local setup (macOS)

```bash
cd "/path/to/RepoLens"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cd frontend && npm ci && npx playwright install chromium && cd ..
# Copy an existing private .env here if one exists; otherwise configure .env.example.
python scripts/phase0_preflight.py
bash scripts/verify_phase11.sh
node start.mjs
```

**Four verification approaches:** Python unit tests; HTTP/integration tests; Playwright E2E browser tests; TDD regression tests (`tests/test_phase11_release_tdd.py`, red-to-green). `scripts/verify_phase11.sh` also runs frontend Node unit tests, GitHub Action tests and Vite production build. The script halts on any failure. Real provider/OAuth/deployment tests require separate operator evidence.

## Production deployment — HTTPS with Caddy

This is a **single-instance reference deployment**, not a claim of live deployment. Requires Docker Compose, a public server, DNS A/AAAA record and open TCP 80/443 plus UDP 443. Configure a new deployment `.env` kept **out of Git**. Use unique production keys, not your Mac's test credentials. `deployment/compose.production.yml` starts Postgres 17, RepoLens backend (with built frontend) and Caddy with automated ACME TLS.

Example configuration keys (values intentionally omitted):

```dotenv
REPOLENS_DOMAIN=
REPOLENS_DB_PASSWORD=
REPOLENS_SESSION_SECRET=
REPOLENS_DATABASE_URL=
REPOLENS_AUTH_DATABASE_URL=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
GEMINI_API_KEY=
GITHUB_TOKEN=
```

Both database URLs must use `postgresql+psycopg://...@database:5432/repolens`; percent-encode special password characters for URL syntax. `REPOLENS_SESSION_SECRET` must contain at least 32 cryptographically random characters; generate offline with `python3 -c 'import secrets;print(secrets.token_urlsafe(48))'`. Set **both** OAuth providers' authorized redirect URIs to `https://YOUR_DOMAIN/api/auth/callback/google` and `https://YOUR_DOMAIN/api/auth/callback/github` as appropriate. Verify issuer/consent and cookies with actual accounts, not only mocked requests. Keep provider keys **server-only**.

```bash
# Run from project root, after secure .env has been configured:
docker compose --env-file .env -f deployment/compose.production.yml config --quiet
docker compose --env-file .env -f deployment/compose.production.yml up -d --build
docker compose --env-file .env -f deployment/compose.production.yml ps
curl -fsSI https://YOUR_DOMAIN/
curl -fsS https://YOUR_DOMAIN/api/health
```

Verify `strict-transport-security`, `x-frame-options`, `x-content-type-options`, cache-control on protected responses and absence of secrets in logs. The container app/database are **not published directly**; all public traffic passes through Caddy. Persist and back up Docker volumes `postgres_data`, `repolens_state`, `caddy_data`. The included `.github/workflows/verify.yml` runs CI checks but does **not** automatically deploy to production.

**Limitations:** local Ollama is not connected to the container by default; if you need local mode on a production host, configure a separately secured private model service. For more than one RepoLens API replica, use `REPOLENS_FRESHNESS_SCHEDULER=external` and one exclusive scheduled worker, and review the persistent index job architecture before scaling. Do not treat this reference compose as a multi-region/high-availability deployment.

## Cold backup, checksum and safe restore — local installation

Stop the RepoLens process and external freshness worker first. State directories include `.repolens_auth`, `.repolens_chroma`, `.repolens_cache`, `reports`, and `.repolens_gallery` (when present); configured external paths are honored. Backups contain credentials/session material and must be encrypted at rest and stored offline. **Never upload a backup to ChatGPT, Git, a public repo, or the public gallery.**

```bash
# Run from project root with .venv activated, server STOPPED:
python scripts/phase11_state.py --backup "$HOME/repolens-private-backup.zip"
python scripts/phase11_state.py --verify "$HOME/repolens-private-backup.zip"
# Restore into a NEW location; existing files can never be overwritten.
python scripts/phase11_state.py --restore "$HOME/repolens-private-backup.zip" --destination "$HOME/repolens-restore-check"
```

Inspect `repolens-restore-check/auth`, `chroma`, `embedding-cache`, `reports` and `gallery-review`. To roll back a failed local deployment, **keep the previous state copy**, stop every RepoLens process, restore from the verified backup to a separate directory and explicitly reconfigure each state path. Preserve your existing `.env` separately in a secure secret manager. This tool refuses symlinks, path traversal, altered file contents and overwriting a restore target. SHA-256 checks integrity, **not** authenticity of an attacker-controlled backup. This utility only backs up local file state; a live Chroma state must not be copied during writes.

## PostgreSQL backup and rollback

**The local backup command does not capture PostgreSQL.** For Compose, first use `pg_dump` and separately verify it using `pg_restore --list`; use restricted permission storage:

```bash
umask 077
# From project root:
docker compose --env-file .env -f deployment/compose.production.yml exec -T database sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -U repolens -d repolens -Fc' > "$HOME/repolens-postgres.dump"
pg_restore --list "$HOME/repolens-postgres.dump" > /dev/null
```

On the actual PostgreSQL host, practice restoring this dump to a **separate empty test database**, validate row counts, login, workspace data and migration rollback before switching production. Keep the old database untouched until the rehearsal passes. For existing local SQLite migration, back up first and use `python -m backend.database.migrate_database --source "$HOME/.repolens_auth"` (dry-run); set `REPOLENS_MIGRATION_TARGET_URL` in a private `.env` pointing at a **new empty** PostgreSQL database, then repeat with `--apply`. Never print database credentials or supply a database URL in shell history. Existing migration is not a reversible down-migration: rollback uses an intact backup/snapshot.

## Cross-feature live acceptance (operator must perform)

1. Two real Google/GitHub users log in and out; verify CSRF, session revocation, role changes, cross-user privacy and all OAuth redirect URIs.
2. Pin a public Python repo (e.g. `pallets/flask`), index it, ask source-cited follow-ups, restart and reload conversation history; change a test branch SHA and re-index.
3. From a controlled PR, verify Diff Analysis and that the GitHub Action **updates one existing comment** on subsequent changes; check fork/permission behavior.
4. Invite a second workspace user, exercise permissions, onboarding assignments, sharing and revocation. Check security scanner advisories and pinned source links. Verify a Python, JS/TS and Go code-flow trace against actual source.
5. With a locally approved private repository, run Ollama embedding and answering. Confirm no Gemini/cloud request and separate embedding indexes.
6. Generate all 20 AI reports, inspect every claim, run manual reviewer approvals and `python scripts/prebuild_gallery.py --publish --require-reviewed`, then verify anonymous access to the deployed pages. Source snapshots are not full AI reports.
7. Force rate limiting and interrupted-job recovery; verify persistent Chroma/cache/job state and worker scheduling after restarts. Execute a migration and rollback rehearsal on dedicated data.
8. Inspect mobile/tablet layout, keyboard focus/accessibility, retries/errors, all public links, TLS and secure cookies in a real browser. Record dated, redacted output per gate.

## Release decision and evidence

Copy `docs/PHASE11_EVIDENCE_TEMPLATE.json` to a private path such as `reports/phase11-evidence.json`. For **each** gate record `{"status":"PASS","evidence":"2026-11-12: command, results and reviewed log/screenshot reference"}`. Do **not** include tokens, names, emails or proprietary source. `FAIL` is appropriate for a reproduced defect; `BLOCKED` means not tested or unavailable.

```bash
python scripts/phase11_gate.py --evidence reports/phase11-evidence.json --output reports/phase11-release.json --strict
# Exit 2 means NOT FULLY VERIFIED; do not publish a stable release.
python scripts/package_release.py "$HOME/Downloads/RepoLens_Phase11_RC.zip"
```

The release script excludes `.env`, `.venv`, `node_modules`, databases, backups, test artifacts, private logs and staged reports; it retains public gallery assets. Release ZIP is a *source distribution*; users still install dependencies and configure their own secrets. To verify that deployment still works after a rollback, rerun the full acceptance walkthrough on a staging host and review the report checksum/source evidence again.
