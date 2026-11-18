# RepoLens Phase 10 — Public Report Gallery implementation and acceptance

## What was actually implemented

- Added **Public Gallery** link to existing dashboard sidebar and public landing page.
- Rebuilt the public gallery in RepoLens's navy, lime and purple visual language, with responsive cards, clear review status, navigation to/from the dashboard, and share/copy-link control.
- Public gallery works without an account, while `Try on your repo` routes to the dashboard (which enforces login).
- Hardened the publication pipeline to invalidate withdrawn or changed approvals and remove stale public Markdown/manifest entries.
- Added verifiable publication receipt checks (source SHA, reviewer, commit and approved staging state when present).
- Added a source-review checklist generator and explicit CLI source-review acknowledgement.
- Made small-batch generation advance past already generated reports to reduce Gemini rate/quota pressure.
- Added test-first unit/regression tests, an HTTP publication integration test, frontend Node tests, and Playwright browser scenarios.

## What is NOT complete without external access

This supplied ZIP contains **20 source snapshots, zero complete reviewed AI architecture reports**. They are explicitly labeled as such. The 20 full AI reports require real GitHub + Gemini/Ollama provider access, successful source analysis at pinned commits, manual accuracy review, approval, and publication. No fabricated reports or approvals were added. No public deployment was performed from this environment. Provider errors may block or delay generation. 

## Generate, review, publish (on your Mac)

With the root `.env` configured and Python dependencies installed:

```bash
python scripts/prebuild_gallery.py --status
python scripts/prebuild_gallery.py --generate --batch-size 2
# Repeat --generate --batch-size 2 to advance through the 20 repositories.
# If any fail, rerun them individually with --repo OWNER/REPO.
python scripts/prebuild_gallery.py --generate --repo pallets/flask
python scripts/prebuild_gallery.py --review pallets/flask
# Open .repolens_gallery/pallets-flask/report.md and REVIEW_CHECKLIST.md;
# verify source links at the recorded SHA and check each checklist item.
python scripts/prebuild_gallery.py --approve pallets/flask --reviewer "Your reviewer name" --acknowledge-source-review
# Repeat the review and approval for EACH generated report.
python scripts/prebuild_gallery.py --publish
python scripts/prebuild_gallery.py --require-reviewed
cd frontend
npm ci
npx playwright install chromium
npm run build
npm run test:browser
```

Reviewing **each** AI report against GitHub source must be done by a human. Automated structural passes and the act of printing a reviewer name are not an accuracy guarantee. `--acknowledge-source-review` is an explicit attestation, not an automated review. Do not approve an unsupported report. Regenerate and correct source errors before approval.

## Four testing techniques

1. **Unit:** `tests/test_phase10_release_tdd.py`, `frontend/tests/phase10-gallery.test.mjs` and existing gallery-link tests cover links, unreviewed warnings, review receipts and revocation.
2. **Integration:** `tests/test_phase10_integration.py` runs a synthetic analysis → staging → source-review checklist → approval → publication → static HTTP GET flow without external model calls.
3. **End-to-end:** `frontend/e2e/phase10_gallery.spec.js` exercises anonymous gallery navigation, report pages, share control and dashboard navigation. Run on your Mac after `npm ci` and Chromium install.
4. **TDD:** The four originally failing Phase 10 release tests were added before implementation, observed failing, then verified passing after the fixes.

**One-command verification:** `bash scripts/verify_phase10.sh` (requires frontend dependencies and Playwright). For the actual 20-report release gate: `REPOLENS_REQUIRE_20_AI_REPORTS=1 bash scripts/verify_phase10.sh`.

## Final acceptance conditions (not yet met here)

- [ ] All 20 reports fully generated using a live provider.
- [ ] Every report reviewed against actual source at its pinned commit, with inaccurate claims corrected.
- [ ] All 20 explicitly approved and published, hashes matching the review receipts.
- [ ] The strict `--require-reviewed` gate exits 0.
- [ ] Public pages work without login in the deployed environment.
- [ ] Source links, copy-link and Try on Your Repo verified in a real browser.
- [ ] Full backend, unit and browser suites pass on the user's Mac and after deployment.

No `.env`, OAuth secrets or embedding databases belong in the public gallery build.
