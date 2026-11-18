# Current delivery

See [RELEASE_2026_10_25.md](./RELEASE_2026_10_25.md) for the authoritative implementation matrix, current test evidence, and exact remaining live steps.

---

## Historical notes (superseded)

# Update your existing RepoLens installation

You do not need a new virtual environment for every downloaded ZIP.
Use this update in your existing project folder to retain your credentials,
accounts, saved conversations, indexes and installed packages.

1. Stop the running project with Ctrl+C.
2. Back up your existing project folder.
3. Extract this ZIP. From the extracted RepoLens folder, run a preview:

```sh
python3 -m backend.cli.apply_update "/absolute/path/to/your/existing/RepoLens"
```

4. Check that the target path is correct, then apply:

```sh
python3 -m backend.cli.apply_update "/absolute/path/to/your/existing/RepoLens" --apply
```

5. Open a terminal in your EXISTING project folder and run:

```sh
source .venv/bin/activate
python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
node start.mjs
```

Use http://127.0.0.1:5173 consistently with your configured OAuth callbacks.
The update preserves your .env and runtime data. Add any desired optional settings
from .env.example without replacing working credentials. Open Knowledge Hub in
the workspace navigation. The public gallery is at /gallery/.

## Knowledge Hub workflows

- Freshness: Build/Refresh an index, or Track existing index if you indexed before
  this upgrade. Check now obtains current status. Re-index updates your recorded
  revision; Explain changes compares the old indexed SHA with the checked SHA.
- PR / Diff: enter a PR number, or leave it blank and enter base/head refs. Open
  saved results later. All AI impact and test suggestions require source review.
- Security: scan a public repo. Read unavailable/unresolved flags and coverage
  limits before interpreting findings. A failed advisory request is not a clean scan.
- Onboarding: create an AI checklist, inspect the verified source quotes and line links, tick tasks, reopen saved results, and export PDF.
- Code Flow: inspect the diagram and evidence table; expand Mermaid source to
  copy it into documentation. No supported path is an explicit result.
- Teams: create a workspace, generate a single-use invitation token, and share it
  yourself. Another signed-in user pastes it into Join workspace. Owners can change
  roles or remove members. Admins share an indexed snapshot; members start a private
  chat on it. Pin only an answer you own with validated citations.

## PostgreSQL (optional; SQLite remains the default)

Install Docker locally and set a new database password in your shell, then:

```sh
docker compose -f compose.postgres.yml up -d
```

The compose file requires REPOLENS_DB_PASSWORD to be set. Add a connection URL to
.env using your password (URL-encode special characters):
`REPOLENS_DATABASE_URL=postgresql+psycopg://repolens:PASSWORD@127.0.0.1:5432/repolens`
For a new empty database, set both REPOLENS_DATABASE_URL and
REPOLENS_AUTH_DATABASE_URL to this URL, restart, then run
`python scripts/check_postgres.py` to exercise conversation/workspace operations.
The real PostgreSQL integration test also exercises auth and migration when
REPOLENS_TEST_POSTGRES_URL points to a dedicated test service.

### Move existing accounts, chats and workspaces

Keep your original auth directory and secret.key. Stop the backend and back up the
whole project first. Set REPOLENS_MIGRATION_TARGET_URL in .env to the EMPTY target
database URL, then run from the existing project folder:

```sh
python -m backend.database.migrate_database --source .repolens_auth
python -m backend.database.migrate_database --source .repolens_auth --apply
```

The first command previews counts without modifying the destination. The second
copies records in one data transaction and checks counts. An occupied destination
is rejected. Source databases are read-only and never deleted. This is a one-time
migration, not ongoing synchronization.

After a successful migration, set REPOLENS_DATABASE_URL and
REPOLENS_AUTH_DATABASE_URL to that same destination and restart. Retain the original
secret.key and OAuth settings. Existing user IDs and unexpired session hashes are
preserved. Keep the backup until you have checked both accounts and saved chats.

## Ollama

Install/run Ollama locally, then pull the two configured models:

```sh
ollama pull llama3.2
ollama pull nomic-embed-text
```

Set REPOLENS_MODEL_PROVIDER=ollama in .env and restart. Build a new index before
asking questions: Gemini vectors cannot be reused for local embeddings. Use the
loopback URL in .env.example. No automatic cloud fallback occurs. GitHub and advisory
requests are still online. The Docker container cannot reach a host Ollama daemon
through its own loopback address; this version's local-provider setup is intended
for running RepoLens directly on the same host as Ollama.

## PR automation and CLI

```sh
python -m backend.cli.main https://github.com/owner/repo --pr 42 --output impact.md
python -m backend.cli.main https://github.com/owner/repo --compare main feature --output impact.md
```

The included .github/workflows/repolens-pr.yml is ready to review and commit in a
repository with RepoLens source at its root and a GEMINI_API_KEY repository secret.
It only runs trusted base code and skips fork/Dependabot PRs. It updates a marked
comment instead of duplicating it. No workflow was installed, executed or published
for you. Review it before enabling provider spending and PR comments.

## Gallery

`python scripts/prebuild_gallery.py` builds all twenty bundled source-snapshot pages.
`python scripts/build_source_gallery.py` refreshes/rebuilds their pinned source receipts; it needs public GitHub reads when evidence is not cached. These are source snapshots, not full AI architecture reports.
`python scripts/prebuild_gallery.py --generate` calls GitHub and your configured
model for the twenty allowlisted public repositories. It consumes provider quota.
Generation stages reports privately, continues after individual failures and
resumes intact completed results. Review each report, approve it with
`--approve OWNER/REPO --reviewer "Your name"`, then run `--publish` to copy only
unchanged approved reports into the gallery. Read FINISH_SETUP.md for the full
generation/review workflow and the independent freshness scheduler.

## Release checks still required

Read RELEASE_READINESS.md and FINISH_SETUP.md before calling the product fully verified. Run real chat,
PR, scan and flow checks on three repositories; inspect citations and retrieval
misses. Run the PostgreSQL checker and local Ollama workflow if using those modes.
Verify OAuth and the new UI in your browser. The hosted chatgpt.site website has
not been updated by this ZIP. No live-service credentials are included.

## Python and Go dependency graph exports

The scanner reads uv.lock/poetry.lock and npm package-lock.json from the repository.
To record an actual Python environment or Go module graph, run these yourself in
the trusted project/environment being audited and make the resulting files available
in the public repository you ask RepoLens to scan:

```sh
python -m pip inspect > repolens-pip-inspect.json
go mod graph > repolens-go-graph.txt
```

Review exports before publishing them; they may contain local paths, private package
names or source URLs. RepoLens parses the recorded data; it never installs or executes
untrusted repository packages to derive a graph. Exact installed environments,
lockfile variants and Go requirement graphs are labelled separately.
