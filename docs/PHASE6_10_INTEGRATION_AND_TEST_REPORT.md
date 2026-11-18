# RepoLens — Phases 6–10 integrated code and verification handoff

**Source baseline:** `RepoLens_RAG_Answers_Citation_Fixed_2026-11-11 (1).zip` (uploaded 11 November 2026).  
**Deliverable:** one merged source ZIP, rather than five incompatible patch ZIPs. The work was organized into six sequential code/test/integration workstreams. There were **no six independent external coding agents** running.

## Executive status

The existing ZIP already implemented the main functionality for Phases 6–10. This handoff **preserves it** and repairs concrete problems proven by failing regression tests. The ZIP contains full project code and the new tests. **Full end-to-end sign-off is NOT yet possible**: the current sandbox lacks Authlib, ChromaDB, native Tree-sitter and frontend Playwright/Vite dependencies, and has no user Gemini/Ollama credentials, repository access, or deployment.

### Workstream 1 — Phase 6: Onboarding checklist generator

- Existing code retained: AI evidence-validated Day 1/Week 1 checklist, first-contribution suggestion, citation paths/lines and exact snippets; DB progress, manager assignments, PDF export, public share/revoke.
- Fixed **duplicate task identifiers** produced by repeated AI tasks at the same source location: duplicate tasks now fail validation rather than share one ID and corrupt completion toggles.
- Enforced bounded first-contribution task and assumption text to avoid runaway model output in persistent/public data.
- Fixed workspace member assignment checkboxes so state changes **optimistically** before the HTTP response and restores the prior value if saving fails.
- Tests: `tests/test_phase6_10_tdd.py`, `frontend/tests/assignmentState.test.mjs` and `frontend/e2e/phase6_10.spec.js`.
- Remaining live acceptance: generate from a real revision, assign to another real OAuth account, record progress and verify persistence, PDF and public share revocation.

### Workstream 2 — Phase 7: Dependency and security surface scanning

- Existing code retained: Python/npm/Go manifests; Python, npm, Go lock/resolution graphs when available; GitHub Advisory lookups; flagged source patterns, possible imports, coverage and truncation warnings.
- Fixed a **false-positive advisory problem**: an exact known version is now checked against a supported vulnerable version range. Safe versions are not labelled affected simply because an advisory mentions the package. Unparseable npm/Go version syntax is explicitly `version_unverified` rather than a made-up finding.
- Added `coverage.unverified_advisories` so unresolved or unverified ranges remain visible.
- Fixed Quick-index coverage: security scanning now independently fetches eligible `requirements.txt`, `package.json` and `go.mod` manifests omitted by the earlier source selection, within size/count and secret safeguards.
- Regression tests exercise safe, affected, unknown-range and omitted-manifest cases.
- Coverage remains deliberately **bounded** (first 60 advisory package records, resolved-artifact and file-size limits). Do not call it a full security certification.
- Remaining live acceptance: GitHub Advisory API responses, current known vulnerable/safe versions, lockfiles, package import coverage and false-positive investigation.

### Workstream 3 — Phase 8: Verified code-flow tracing

- Existing Python AST and native Tree-sitter JS/TS/Go parsers, inferred/confirmed source links, Mermaid serialization and React diagram retained.
- Added explicit **source-confirmed literal HTTP route-decorator → handler** entry links for common Python router decorators. The representative diagram now begins at the route where a literal route is available; downstream links still require their own source evidence.
- This establishes that a handler was *declared* under that decorator, **not** that the route is mounted or reachable at runtime.
- Regression test checks exact route line, handler, service call and Mermaid source.
- Remaining live acceptance: native Tree-sitter languages installed and tested on actual Python/JS/TS/Go repositories, including dynamic-call caveats and independent source review.

### Workstream 4 — Phase 9: Local Model Mode (Ollama)

- Existing Gemini/Ollama selection, provider-specific embedding indexes, loopback-only Ollama request transport, ChromaDB embedding separation, local snapshot permissions, secret filters and local file citations retained.
- Fixed a **security-sensitive authorization bug**: if the configured `users` allowlist was accidentally a string instead of an array, substring matches could grant access (`ali` matched `alice`). Only explicitly listed user IDs in a real array may now access a private local directory.
- A regression test demonstrates the denied unauthorized access.
- `scripts/check_ollama.py --live` is the provider probe, but is **not executed** here. Real machine must run and pull both generation and embedding models. Cloud egress/privacy verification is a separate live requirement.

### Workstream 5 — Phase 10: Public report gallery

- Existing 20 **source snapshots**, resumable full AI report generation, approval, hash checking and publish pipeline retained. No fabricated AI reports were added.
- Fixed a recovery issue: an API failure during `--force` regeneration no longer wipes an already approved and unchanged report's approval state.
- Added safely escaped, readable Markdown with only allowlisted GitHub HTTPS source links; untrusted HTML and `javascript:` links do not execute.
- Added `--require-reviewed` **strict release gate**. It fails until the configured twenty repositories each have an approved, hash-matched, published AI architecture report; source snapshots do **not** count.
- Updated Node/browser tests to accept either correctly labelled snapshots or reviewed AI reports instead of hardcoding snapshots forever.
- **Current true status: 0 of 20 manually approved, published full AI reports**. The included 20 source-snapshot pages remain public examples but do not satisfy Phase 10's acceptance condition.
- Remaining live acceptance: real model generation, per-report source review, approval, publication, SEO and public deployment checks.

### Workstream 6 — Merge and compatibility

- Merged modifications into the uploaded source tree, retaining existing OAuth, RAG fixes, workspace permissions, PR Action and dashboard architecture.
- Added `scripts/verify_phase6_10.sh` to run the complete automated verification on a Mac after dependencies are installed.
- Added browser acceptance tests for Phase 6 assignment persistence UI, Phase 7 advisory status, Phase 8 route graph and Phase 9 local Q&A UI. These tests are **auth/provider-mocked UI checks**, not real cloud/Ollama certification.
- Updated the historical gallery browser assertion to check readable content instead of requiring one raw `<pre>` tag.

## Actual test evidence in this environment

| Check | Result | Qualification |
|---|---|---|
| Test-first regressions | **10/10 passed** after fixes | Initially 8 failing, then 2 additional failing cases |
| Relevant existing + new Python suite selection | **63 passed, 8 deselected** | Deselections involve Authlib and native Tree-sitter-dependent tests |
| Frontend Node unit tests | **21 passed** | Includes new assignment-state tests |
| GitHub PR-comment Node tests | **3 passed** | Unchanged Phase 4 functionality retained |
| Python source compilation | **Passed** | Syntax compilation only |
| Gallery HTML generation | **20 snapshot pages built** | **0/20 reviewed AI reports** |
| Strict gallery approval gate | **Correctly blocked (exit 2)** | Expected until 20 manual reviews/publications |
| Full Python suite | **NOT run successfully** | This sandbox lacks Authlib; cannot claim a pass |
| Frontend Vite production build / Playwright | **NOT run** | Frontend node_modules and Playwright unavailable; npm offline cache incomplete |
| Real Gemini / Ollama / GitHub API | **NOT run** | Private keys, local daemon and GitHub state not supplied |
| Real deployed public gallery | **NOT deployed** | Requires a hosted environment, verified reports and approval |

These results should not be added together as if they were one non-overlapping test suite; the 10 new tests also appear in the 63 selected Python tests.

## Mac verification — from the project root

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
(cd frontend && npm ci && npx playwright install chromium)
bash scripts/verify_phase6_10.sh
```

This script runs preflight, Python pytest, Node PR tests, frontend Node tests, production Vite build, Playwright browser tests, and gallery status. Preserve your old `.env`, authentication database and ChromaDB index in backups before replacing any working installation. The ZIP intentionally contains **no private credentials or runtime databases**.

### Required live tests before marking phases complete

1. **Phase 6:** `Knowledge Hub → Onboarding` on a real indexed GitHub repository; assign to a second account through Teams, toggle completion, reload, download PDF, share publicly, revoke and confirm an old URL returns 404.
2. **Phase 7:** `Knowledge Hub → Security` against a repository with pinned safe and known vulnerable dependencies and resolution artifacts. Verify version matching, import lines and incomplete-scan flags with live GitHub Advisories. The hard 60-package cap must be evaluated against the intended deployment and increased only with rate-limit budgeting and correct pagination.
3. **Phase 8:** `Knowledge Hub → Code Flow` on real Python, JS/TS, Go repos. Compare each CONFIRMED edge to its source snippet and check INFERRED/uncertain paths are clearly labelled.
4. **Phase 9:** Configure `.env` `REPOLENS_MODEL_PROVIDER=ollama`, pull/configure generation and embedding models (e.g. `llama3.2` and `nomic-embed-text`), and set `REPOLENS_LOCAL_REPOSITORIES` to explicitly approved absolute local directories and user IDs. Restart, run `python scripts/check_ollama.py --live` or set `REPOLENS_VERIFY_OLLAMA=1` for the verification script. Index privately, ask sourced questions, revoke a user, confirm no cloud AI requests.
5. **Phase 10:** Run `python scripts/prebuild_gallery.py --generate` (provider quota required; resumable), `--status`, manually inspect every staged report and compare source evidence, then `--approve OWNER/REPO --reviewer YOUR_REVIEWER_NAME` for each individually, `--publish`, and finally `python scripts/prebuild_gallery.py --require-reviewed`. Only after its exit code is 0, rebuild the frontend, deploy publicly, and inspect public URLs, sharing, and SEO metadata. Source snapshots alone cannot satisfy this phase.

**Required end state:** No mock-only evidence is treated as proof of a live integration. Phase 10 remains **blocked** until 20 reports have genuinely been AI generated, manually inspected, approved and published. Other phases also require the real acceptance checks above.
