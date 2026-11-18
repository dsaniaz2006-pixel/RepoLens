# RepoLens Section 5 — Verification report

## Result

**Source-code implementation complete. Full production acceptance pending.**

### TDD (RED, then GREEN)

Before implementation, `tests/test_section5_tdd.py` reported 2 failing tests
and 2 passing tests. The failures showed that a follow-up referring to
"question 2" retrieved the wrong older turn after the last-12-message context
window rolled forward, and `contextual_query` had no explicit reference input.

The new frontend test initially failed because the safe citation-link helper
had not been implemented. Both test sets are now green.

### Tests executed in this environment

| Test scope | Result |
|---|---|
| Section 5 and existing conversation/retrieval/grounding focused suite | 27 passed |
| Opt-in disposable PostgreSQL integration | 1 skipped: no test database configured |
| Frontend Node unit suite, including 3 new Section 5 assertions | 33 passed |
| Broader backend suite (excluding real OAuth tests) | 405 passed, 4 failed, 6 skipped |
| Baseline comparison on the untouched Section 4 ZIP | Same four failures reproduced |
| Full React/Vite build | Not run: dependency installation unavailable |
| Playwright browser E2E | Written, syntax checked, **not executed** |
| Real Gemini/Neon browser acceptance | Not run: private credentials live on user's Mac |

**Important:** The broader backend suite used a test-only no-op OAuth
registration shim to permit FastAPI import while Authlib was unavailable in the
offline test runner. It did **not** validate Google/GitHub OAuth. The Section 5
HTTP tests do exercise real FastAPI routes, session cookies, CSRF handling and
SQLAlchemy/SQLite persistence, with only GitHub, retrieval and AI responses mocked.

### Existing unrelated failures (reproduced in original Section 4 ZIP)

- `tests/test_completion.py::test_non_python_flow_is_explicitly_inferred` on
  `.js`, `.ts`, and `.go` sources (3 cases).
- `tests/test_product_upgrade.py::test_public_gallery_is_accessible_without_account`
  (FastAPI returns 404 for `/gallery/`, which is a static frontend route).

### Run on user's Mac from the extracted project root

```bash
source .venv/bin/activate
python -m pytest -q \
  tests/test_section5_tdd.py \
  tests/test_section5_api_integration.py \
  tests/test_conversations.py \
  tests/test_retrieval_fix.py \
  tests/test_qa_source_grounding_tdd.py

cd frontend
npm ci
npm test
npm run build
npx playwright install chromium
npm run test:browser -- e2e/section5_conversations.spec.js
cd ..
```

The opt-in live PostgreSQL test **creates and drops a schema**. Only run it
against an isolated test database/branch:

```bash
# Set REPOLENS_TEST_POSTGRES_URL privately to a disposable Neon branch/database.
python -m pytest -q tests/test_section5_postgres_integration.py
```

### Live acceptance checklist

1. Back up Neon and preserve the working Section 4 folder before changing source.
2. Open the revised app, sign into your existing account.
3. Index a public repository and start a new conversation.
4. Ask two related questions; confirm that the second reuses context and cites
   files in the indexed commit.
5. After at least seven turns, ask a question referring specifically to
   "the function from question 2" and confirm the answer addresses question 2.
6. Restart RepoLens and verify the full saved conversation and citations remain.
7. Use a second account and verify that it cannot list/read/delete or ask through
   the first account's conversation.
8. Run the Playwright and isolated PostgreSQL tests successfully.

No changes are made to the user's live Neon database by packaging this ZIP.
