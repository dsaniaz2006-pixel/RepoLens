# Phase 6 — Gemini transient 503 handling

## Symptom
`python scripts/check_onboarding_provider.py` reported `PROVIDER FAILURE: Gemini service unavailable (HTTP 503)`. This means Gemini could not serve that request; it does not establish that the user API key or onboarding JSON validation is wrong.

## Code change
`backend/ai/model_provider.py` now makes up to three generation attempts for **Gemini 500/502/503/504 only**, with 1- and 2-second delays. It retains strict JSON parsing and source citation checks and never retries 429 quota, 400 bad input, 401/403 authentication, 404 missing model, or local Ollama errors automatically. Persistent outages still return the explicit HTTP status. No raw provider error or key is included in the user-facing exception.

## Tests
`tests/test_onboarding_model_reliability.py` includes TDD-style cases for two transient failures followed by success, repeated 503 failures, quota non-retry, and Ollama non-retry. 27 selected tests passed in the build environment (onboarding + Phase 6–10 TDD). This does not replace the full Mac/Playwright or live provider verification.

## Verify on macOS
1. Back up your current RepoLens folder. Unzip this release in a new directory. Reuse your `.env` and authorized local runtime data carefully, keeping them outside the distributable ZIP.
2. `python3 -m venv .venv && source .venv/bin/activate && python -m pip install -r requirements.txt`
3. `python -m pytest -q tests/test_onboarding_model_reliability.py tests/test_phase6_10_tdd.py`
4. `python scripts/check_onboarding_provider.py`
5. If it still returns HTTP 503 after all retries, Gemini remains unavailable. Retry later or use a known-accessible provider/model. Do not repeatedly hammer a failing service. If the smoke test passes, start RepoLens and generate a real checklist, then check citations and persistence.
