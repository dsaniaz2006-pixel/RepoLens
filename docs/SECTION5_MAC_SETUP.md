# RepoLens Section 5 — Mac setup and verification

## Step 1 — Protect the working Section 4 project

Keep your `RepoLens 4` folder unchanged. Create a Neon backup/recovery branch
for safety. Do not copy `.venv` or `node_modules` between projects.

## Step 2 — Unzip the new project and copy environment configuration

Extract `RepoLens_Section5_MultiTurn_Conversations_2026-11-13.zip` to a new folder
and open the extracted `RepoLens` root in VS Code. Copy the private `.env` from
`RepoLens 4` into the extracted **root**. Never paste `.env` or the Neon connection
string into chat, screenshots or Git.

## Step 3 — Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
```

Section 5 does not add migrations, so `auth_0004` and `app_0001` should still be
valid. Verify (without upgrading unless instructed):

```bash
python -m backend.database.schema_migrations verify
```

## Step 4 — Tests

```bash
python -m pytest -q tests/test_section5_tdd.py tests/test_section5_api_integration.py \
 tests/test_conversations.py tests/test_retrieval_fix.py tests/test_qa_source_grounding_tdd.py
cd frontend
npm test
npx playwright install chromium
npm run test:browser -- e2e/section5_conversations.spec.js
cd ..
```

The opt-in real PostgreSQL test requires a SEPARATE disposable test branch and
`REPOLENS_TEST_POSTGRES_URL` in your local environment. Never use the production
`neondb` credentials for a destructive test.

## Step 5 — Run and verify

Stop the previous RepoLens backend/frontend by pressing Ctrl+C in their owning
terminals. Check port owners before stopping any process:

```bash
lsof -nP -iTCP:8000 -iTCP:5173 -sTCP:LISTEN
```

Start the new project from its root:

```bash
node start.mjs
```

Open the URL reported by the launcher (normally `http://localhost:5173/dashboard/`)
and navigate to Conversations. Build/refresh a RAG index, create a chat, ask a
follow-up, refresh, and restart. Check that citation links are pinned to the
saved SHA and that the right earlier question is used.

## External verification

No additional online service is needed if Gemini, GitHub OAuth and Neon are
already configured. To confirm actual AI grounding, real provider access and
an indexed repository must be working on your Mac. A second account is useful
to verify private conversation isolation. Full Stripe/payment setup is not
part of Section 5.
