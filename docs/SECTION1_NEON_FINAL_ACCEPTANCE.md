# RepoLens Section 1 — Neon live acceptance (read-only first)

This procedure does not require sharing your Neon password with ChatGPT, Codex, or GitHub. Keep your existing `RepoLens 13` folder and `repolens_backup/.repolens_auth` backup untouched.

## A. Confirm your actual Neon records, without modifying them

From the project root, with `.venv` active and your private `.env` already configured:

```bash
python scripts/verify_section1_neon.py --source repolens_backup/.repolens_auth
```

Look for `"pass": true`, `"connected": true`, and both `"up_to_date": true`. The tool compares *identity keys*, not just total row counts, for users, conversations, messages, saved items and workspace memberships when they exist in the backup. No passwords, emails, user IDs, or session tokens are printed. It only performs SELECT/inspection operations and does not run migrations.

From the screenshot of the dry-run migration, the original source had **1 user, 1 session, 0 conversation messages and 0 conversations**. If you see no historical conversation/workspace records in the backup, the data comparison cannot establish those user journeys; test them live using part B.

If the tool returns a failure, do not attempt to re-run a destructive migration. Share the sanitized JSON output (check before sharing), not the private `.env`.

**Note:** `index_jobs.sqlite3` was backed up, but the Section 1 one-shot migration tool does not migrate that job-history database into Neon. Do not claim that all historical indexing jobs moved to PostgreSQL.

## B. Validate the website is using Neon (manual OAuth acceptance)

1. Shut down any old server, then start the new project from the root using `node start.mjs`. Check the process is the newly started backend rather than a stale port-8000 server.
2. Sign in with your existing Google/GitHub account. Confirm that you are not being treated as a new user (same account data and permissions).
3. Start an analysis on a repository for which a RAG index exists, open a new chat and send a short question. Refresh the page. The conversation and its messages should remain. If live Gemini is unavailable, use a previously functioning index rather than claiming Gemini success.
4. Create a workspace called `Neon Persistence Test`. Refresh the page; confirm you are still the owner.
5. Stop RepoLens, start it again and log in. Confirm the chat and workspace are still available. This checks full UI/backend/database persistence across restart.
6. Open the Neon Console's **Tables** view. Confirm `users`, `conversations`, `conversation_messages`, and `workspace_members` show the new records.
7. Run `python scripts/verify_section1_neon.py --source repolens_backup/.repolens_auth` again. Your online counts may be **higher** than backup counts (new data is expected).

## C. Automated tests on your Mac

```bash
python -m pytest -q \
  tests/test_section1_live_verify.py \
  tests/test_section1_migrations.py \
  tests/test_section1_cli.py \
  tests/test_section1_database_e2e.py

cd frontend
npm ci
npm test
npm run build
npx playwright install chromium
npm run test:browser
cd ..
```

Playwright's existing tests mostly mock backend HTTP responses. They validate browser UI behavior but **do not prove the real Neon database works**. Complete Part B as well.

## D. Real PostgreSQL integration test (use a separate disposable Neon branch/database)

Do **not** point destructive automated integration tests at the production branch. In Neon, create a new child branch called `repolens-section1-test` (if branching is offered in your plan), obtain its **direct connection string**, and configure it only in your local terminal for that test. Use a dedicated database or branch where create/drop of temporary schemas is acceptable.

```bash
# Interactive entry avoids writing a secret into your shell history.
read -s 'REPOLENS_TEST_POSTGRES_URL?Paste the disposable test DB direct URL: '
export REPOLENS_TEST_POSTGRES_URL
printf '\n'
python -m pytest -q tests/test_postgres_integration.py
unset REPOLENS_TEST_POSTGRES_URL
```

This integration test intentionally creates and drops a temporary PostgreSQL schema. It is not a read-only test. Do **not** use a real user's active production database URL.

The URL should begin with `postgresql+psycopg://` (replace only the prefix if Neon gives `postgresql://`) and keep Neon's TLS query parameters.

## E. When Section 1 is complete

- The read-only Neon acceptance script passes and source identities are preserved.
- You can log in as the original user.
- Newly created chats and workspaces survive a full backend restart.
- Dedicated PostgreSQL integration tests pass.
- Frontend unit/build/browser tests pass on your Mac.
- Any preexisting `index_jobs.sqlite3` job history is accounted for separately, if that history matters to your release.

TDD refers to the test-first development process (red then green), not an extra type of runtime test. It cannot replace the real integration and acceptance checks above.
