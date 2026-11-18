# RepoLens Phase 6 — Onboarding JSON failure fix

## Observed incident

The user's `POST /api/checklists` returned HTTP 400 with the generic message
`Model request failed or returned invalid JSON; check provider access and quota`.
The previous `json_model` caught all provider and JSON errors and replaced them
with one message. The onboarding prompt included the **entire** selected source
files, which can substantially exceed practical output/context limits.
No original Gemini exception was available in the provided browser screenshot,
so the exact live provider failure cannot be asserted retrospectively.

## Changes

- `backend/ai/model_provider.py`: safe structured failure categories for HTTP
  429 quota, 400 request, 401/403 auth, 404 invalid model, 5xx, timeout,
  empty output, and malformed/non-object JSON. Original SDK messages, source
  and tokens are never returned to the browser.
- `backend/api/product_api.py`: correct, actionable HTTP statuses for provider
  failures rather than interpreting every model issue as client HTTP 400.
- `backend/services/onboarding.py`: prioritize useful source excerpts, include
  exact original line numbers, and bound model input to 23,000 characters.
  Keep the full original source **server-side** for strict exact-quote checks.
  On malformed JSON or failed quote validation, allow one bounded regeneration.
  Quota, authentication, and transport errors are **not** retried.
- `tests/test_onboarding_model_reliability.py`: new regressions for compact
  prompts, validated quotes, quota behavior, JSON parsing, and one repair.
- `scripts/check_onboarding_provider.py`: optional small *live* structured
  generation test, no GitHub or DB writes and no credential logging.

## Mac commands

```bash
source .venv/bin/activate
python -m pytest -q tests/test_onboarding_model_reliability.py tests/test_completion.py -k 'onboarding or provider or test_model'
python -m pytest -q
cd frontend && npm ci && npm test && npm run build && npm run test:browser
cd ..
python scripts/check_onboarding_provider.py
node start.mjs
```

The `check_onboarding_provider.py` command calls the configured Gemini/Ollama
provider and consumes its normal model quota. The new ZIP intentionally omits
`.env`, `.venv`, `node_modules`, local accounts and index databases. Copy your
private configuration and back up persistent data before swapping project dirs.

## Acceptance gates

1. All backend/frontend/browser suites pass on macOS.
2. Live provider smoke test returns two source-verified tasks.
3. Real Flask onboarding creates a persisted checklist with valid source lines.
4. Progress survives browser refresh and server restart, assignment, PDF export,
   share and revoke are verified separately.
5. HTTP 429, 502, 503, and 504 (when applicable) expose safe, actionable error
   descriptions rather than the old generic HTTP 400.

The offline tests and syntax checks do not certify live Gemini quota or end-to-
end onboarding success. No model prompt or error handling can bypass an actual
provider quota or account permission limit.

## Verification record in the patching environment

- New and existing focused Python tests: **28 passed** (10 unrelated tests deselected).
- Existing frontend Node unit/regression tests: **26 passed**.
- Python source compilation: passed.
- Broader backend test attempt: 270 passed, 3 skipped, 7 failed and 19 errors in
  the restricted patching environment. Authlib is absent and the installed
  native Tree-sitter parsers are not present; the corresponding failures are
  outside these changes. The full suite must run on the user's Mac.
- Browser Playwright, live Gemini/Ollama and real Flask checklist creation:
  **not executed** in the patching environment; these remain acceptance gates.
