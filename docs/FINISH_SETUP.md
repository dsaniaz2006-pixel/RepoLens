# Finish setup and verify the real services

Use this guide after applying the source update in START_HERE.md. Commands below
run from your existing RepoLens project folder with its virtual environment active.
Keep your working `.env`, accounts and indexes there. The delivered ZIP contains
an empty credential template, not working accounts or API keys.

## 1. Install the update and start it

```sh
source .venv/bin/activate
python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
npm test
cd ..
python -m pytest -q
node start.mjs --check
node start.mjs
```

For a new installation only, create `.venv` with `python3 -m venv .venv`, activate
it and copy `.env.example` to `.env` before installing. Do not overwrite a working
`.env` during an update. Open the origin specified by REPOLENS_BASE_URL, normally
http://127.0.0.1:5173.

If backend port 8000 is occupied, stop your own previous terminal with Ctrl+C, or
run `node start.mjs --backend-port 8010`. The launcher checks ports before starting;
it does not kill another program. The backend override also updates Vite's API
proxy. Leave the browser origin unchanged so existing OAuth callbacks still match.
To change the browser port, change REPOLENS_BASE_URL and both providers' callback
URLs together. Restart after changing `.env`.

## 2. Complete Google and GitHub signup/login

Open AUTH_SETUP.md for the provider console screenshots-independent instructions.
Use **your own** web OAuth application IDs and secrets in these server-only fields:
GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET.
A Google client ID must be copied in full, including `.apps.googleusercontent.com`.
A suffix alone is not a client ID. Never paste a client secret into a client ID field.

With the default origin the exact callbacks are:

- Google: `http://127.0.0.1:5173/api/auth/callback/google`
- GitHub: `http://127.0.0.1:5173/api/auth/callback/github`

For Google use a **Web application** OAuth client, the matching client secret and
consent configuration. If the app is in Testing, add your Google account as a test
user. Use the same project/client for both values. GitHub needs an **OAuth App**;
a personal access token is not its client secret. After saving `.env`, restart and
run `python scripts/check_auth.py`. "Credentials present" only checks configuration.

In a private browser window, open `/signup/` and choose Google. Approve consent;
confirm the dashboard appears. Log out and repeat via `/login/`. Repeat with GitHub
in another browser profile. An anonymous request to `/api/workspaces` must return
401; private dashboard data must remain unavailable until authentication. Existing
provider accounts log in through the same buttons; first use creates the account.

For a 401 from Google, inspect the **provider's exact error text**: `invalid_client`
means mismatched/deleted client credentials or wrong client type; `redirect_uri_mismatch`
means the callback differs; `access_denied` can mean consent/test-user restrictions.
Do not guess by replacing only the client ID suffix. Browser callback configuration
must be changed to your real HTTPS origin when deployed.

## 3. Verify the selected model and real answers

For Gemini, enter your real GEMINI_API_KEY locally, select
REPOLENS_MODEL_PROVIDER=gemini, then run:

```sh
python scripts/check_models.py --live --probe
python scripts/evaluate_repositories.py --live
python scripts/evaluate_rag.py --live --build-indexes --resume --batch-queries --output reports/rag-current.json
python scripts/evaluate_qa.py --live --output reports/qa-current.json
python scripts/verify_live_persistence.py --evaluation reports/rag-current.json --output reports/chroma-current.json
```

These commands contact providers and consume quota; report/index commands transmit
selected public repository source to the configured model. The release process did
not use the removed uploaded key. If a provider rejects a model, fix access/quota
for the configured model before continuing; do not count a failed probe as a pass.

Read the generated report claims against pinned GitHub source links. For retrieval,
inspect each labeled question's expected paths and retrieved chunks, not just the
aggregate score. Record a real missed path, its cause, the code/settings change,
and a rerun of **the same question at the same SHA**. Preserve before/after JSON.
A synthetic regression is useful but is not a substitute for that live experiment.
If no miss occurs, report that fact instead of manufacturing one.

In the UI, build an index and wait for the completed progress state. Ask three
*different* source questions and a follow-up in one saved conversation; verify each
citation opens the correct file, commit and lines. Ask an unrelated unanswerable
question: the answer must acknowledge insufficient evidence. Reopen the conversation
after restarting the server. Delete a conversation and verify it stays deleted.
If two questions have the same answer, record both questions, answers and retrieved
chunks before changing prompts; test retrieval and question submission separately.

For Ollama, run RepoLens and Ollama on the same computer, install/pull the selected
models, set REPOLENS_MODEL_PROVIDER=ollama, then restart:

```sh
ollama pull llama3.2
ollama pull nomic-embed-text
python scripts/check_ollama.py --live
```

Build a **new** index for this provider and repeat the UI answer/citation check.
The local mode has no automatic Gemini fallback. GitHub/advisory access still uses
the network. Local model quality and hardware capacity need your own measurement.

## 4. Run freshness checks even when the web server is stopped

Freshness state and the worker lease live in the configured database. Indexed and
shared repositories are checked every six hours; failed requests retry after 15
minutes. The worker polls every five minutes. It detects a changed commit and marks
the repository stale; it does not silently rebuild indexes or send email.

```sh
python scripts/freshness_worker.py --once
```

For a durable **macOS** login schedule, use the project's `.venv`, set
REPOLENS_FRESHNESS_SCHEDULER=external in `.env`, and run:

```sh
python scripts/install_freshness_schedule.py --write
```

The command prints the exact plist path. Load that path with
`launchctl bootstrap gui/$(id -u) "/the/printed/path.plist"`.
Inspect `.repolens_logs/freshness.log` for JSON results. To remove the schedule, run
`launchctl bootout gui/$(id -u) "/the/printed/path.plist"` and remove that plist.
Move the project only after unloading the old schedule. Linux/hosting platforms can
schedule the same `freshness_worker.py --once` command with their scheduler; supply
the same database URL and project directory. Only one worker claims the database
lease at a time. A logged-out, sleeping or powered-off Mac cannot perform network
checks; use an always-on host for those conditions.

Acceptance: index your own public test repository, push a harmless README commit,
run Check now in the UI, and verify the stale flag and both SHAs. For scheduled
acceptance wait until a record is due, stop the API, run the standalone worker and
restart the UI; the persisted status should show the changed SHA. Re-index and
verify the stale flag clears. Inspect errors if GitHub access is rate limited.

## 5. Verify PostgreSQL, migration and two-account permissions

SQLite is supported and remains the default. To use PostgreSQL, install Docker,
set your own strong REPOLENS_DB_PASSWORD in your shell, then run:

```sh
docker compose -f compose.postgres.yml up -d
```

Wait for `docker compose -f compose.postgres.yml ps` to show a healthy database.
Follow START_HERE.md to migrate existing data **before** switching either database
URL. Stop the API and back up the project first. The migration copies accounts,
unexpired session hashes, conversations, workspaces and checklist sharing tokens;
lease ownership is reset. It previews by default and refuses an occupied destination.
Keep the original secret.key and directories until verification is complete.

For fresh data, set REPOLENS_DATABASE_URL and REPOLENS_AUTH_DATABASE_URL to the
same PostgreSQL URL in `.env`; URL-encode password characters. Restart and run
`python scripts/check_postgres.py`. This writes and cleans up isolated test records.
For the migration/auth integration test, use a **separate empty test database** and
set REPOLENS_TEST_POSTGRES_URL in your terminal, then run:

```sh
python -m pytest -q tests/test_postgres_integration.py
```

Unset the test URL afterward. The included verify.yml CI workflow provisions its
own test database and runs this test plus browser checks. A skipped service test
is not a PostgreSQL pass.

Use two browser profiles/accounts: A creates a workspace and invitation; B joins
with the single-use token. B must not edit roles or read A's private chats. A can
share an indexed snapshot; B can start a private conversation on it. A revokes B;
B must lose workspace access. Checklist links are explicit read-only sharing:
create one, open anonymously, revoke it, and verify the old URL returns 404.
Invitations currently use manually shared tokens, not emailed invitations.

## 6. Exercise large diffs, onboarding, security and flow

PR / Diff: use a real small PR, then a large PR from a public repository. Confirm
coverage counts, batches, omitted paths and incomplete-patch warnings. Compare
main/feature refs and verify both output SHAs. Only supplied evidence can be cited.
REPOLENS_DIFF_MAX_BATCHES controls 1–32 model calls (default 8); raising it increases
cost and runtime. GitHub caps PR files at 3,000 and compare files at 300; the app
shows incomplete coverage. It cannot infer unseen patches. Long requests may exceed
reverse-proxy timeouts; use the CLI command in START_HERE.md for large analyses.

Onboarding: generate a checklist, inspect the task-specific quoted source lines,
complete a task, reload, export PDF, and test explicit public sharing/revocation.
Fabricated paths/quotes are rejected rather than presented as verified evidence.

Security: inspect exact versions, advisory failures and unresolved graph warnings.
For Python/Go graphs use lock files or the trusted-environment exports described
in START_HERE.md. The app never installs untrusted dependencies to resolve them.
A dependency graph is not proof that every vulnerable path is exploitable.

Flow: test Python imports/aliases and instance methods plus a supported non-Python
project. Inspect CONFIRMED/INFERRED/UNRESOLVED links and source lines. Runtime-only
resolution, dynamic dispatch, reflection and every possible language are not
complete static call graphs; they remain explicit limitations.

## 7. Generate, review and publish the 20 full AI gallery reports

The twenty bundled examples are commit-pinned **source snapshots**. They are not
full reviewed AI architecture reports. Generate the requested full versions with
your working provider; start with one repository:

```sh
python scripts/prebuild_gallery.py --generate --repo pallets/flask
python scripts/prebuild_gallery.py --status
```

Inspect `.repolens_gallery/pallets-flask/report.md` and its pinned source links.
Verify architecture, reading path, flow claims and improvement assumptions. Then:

```sh
python scripts/prebuild_gallery.py --approve pallets/flask --reviewer "Your name"
python scripts/prebuild_gallery.py --publish --repo pallets/flask
python scripts/prebuild_gallery.py --generate
```

The final command generates/resumes all twenty, continues after individual failures,
and retains completed reports. Inspect state.json for a safe error_type; fix the
provider/quota problem and rerun. To refresh an already generated report deliberately,
use --force with --repo; it requires a new review. Successful generation is a
structural evidence check, not proof of semantic correctness. Changing the staged
report after approval invalidates publication.

Review each remaining report and run --approve for its exact owner/repo. Run
`python scripts/prebuild_gallery.py --publish` after those reviews. Only approved,
unchanged reports are copied into the public gallery; failed/unapproved entries
retain their previous public example. Run `cd frontend` then `npm run build` and
publish that build with the backend. The public labels distinguish snapshots and
reviewed AI reports. No script automatically invents a human review.

## 8. Enable a real PR comment and deploy

Commit the updated source and `.github/workflows/repolens-pr.yml` to your repository's
default branch. Add your real GEMINI_API_KEY in repository Settings → Secrets and
variables → Actions. Allow the workflow's requested pull-request write permission.
Open a same-repository PR after the workflow is on the default branch. Inspect the
Actions log and its marked RepoLens comment; push another commit and confirm the
same comment updates. Fork and Dependabot PRs are deliberately skipped. An uploaded
workflow file alone is not evidence it ran. Marketplace publication is a separate
public release step and has not been performed.

Deploy the backend and built frontend behind the **same HTTPS origin**, proxy /api
to the backend, preserve auth/database/index directories, and set REPOLENS_ENV=production,
REPOLENS_BASE_URL to your real origin and a private random session secret of at
least 32 characters. Register that origin's exact OAuth callbacks. Set deployment
secrets on your host, not in frontend code or a ZIP. Repeat OAuth, private-page,
CSRF, index progress, citation, sharing and restart checks on the deployed origin.
This source ZIP does not update the previously linked chatgpt.site deployment.
