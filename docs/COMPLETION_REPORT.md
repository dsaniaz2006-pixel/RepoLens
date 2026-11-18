# Current delivery

See [RELEASE_2026_10_25.md](./RELEASE_2026_10_25.md) for the authoritative implementation matrix, current test evidence, and exact remaining live steps.

---

## Historical notes (superseded)

# Historical RepoLens completion-fix report

This describes a previous revision. Read RELEASE_READINESS.md for this release's
fresh verification and FINISH_SETUP.md for the remaining operational steps.
Source: the last saved RepoLens_Roadmap_Upgrade.zip and the user's follow-up audit.

## Concrete audit gaps closed

| Audit issue | Change | Evidence |
|---|---|---|
| PR ranking differed from the PDF | PR patches now use file_selector.filter_and_rank scores and its safety exclusions; each selected patch records selection_score. | Regression test checks source outranks a much larger documentation change and excludes .env. |
| Generic onboarding tasks and line 1 links | AI-generated Day 1/Week 1 tasks now require exact 1–3 line source quotes, verified paths and real line numbers; invalid evidence fails before saving. Why/snippet appear in the UI. | Valid-line, invented-file, wrong-line and fabricated-quote tests; checklist API persistence/PDF regression. |
| SQLite-only authentication | REPOLENS_AUTH_DATABASE_URL supports PostgreSQL through a parameterized SQLAlchemy adapter. Default SQLite behavior is retained. | Identity/upsert/revocation test against the adapter; all existing auth tests pass. Real PostgreSQL service test included in CI, not run here. |
| No account/chat migration | migrate_database.py previews and atomically copies users, session hashes/CSRF/expiry, chats/messages and workspace data into an empty destination. IDs are preserved; source files are read-only; an occupied destination is rejected. | Full SQLite-to-SQLite migration regression; CI exercises SQLite-to-PostgreSQL when its service runs. |
| Python/Go transitive graph inputs missing | Added uv.lock/poetry.lock, pip inspect JSON and go mod graph text adapters. Resolved transitive packages join bounded advisory checks. npm lockfile support retained. | Python transitive, Go transitive, uv.lock and npm graph tests. |
| Flow limited to top-level Python | Added Python imports/aliases, relative-module and class-method resolution; tree-sitter extracts JavaScript/TypeScript/Go source calls. Mermaid/diagram/evidence output retained. | Python alias/method and JS/TS/Go tests. Unproven non-Python links are explicitly INFERRED. |
| Only three gallery reports | Generated twenty real commit-pinned public-source reports and all twenty public pages, with source checksums and declaration line links. | Live public GitHub reads for all twenty; twenty-receipt/page integrity regression. |
| Conflicting status documents | CHAT_UPGRADE.md and UPGRADE_STATUS.md now refer to this current report. Older status files are prominently labelled historical. | Documentation updated in this ZIP. |

`action.yml` now also provides a reusable composite action that generates a report
without executing PR code. Its output can be reviewed before the caller posts it.
Marketplace publication remains a repository-owner release step.

## Important boundaries

The twenty gallery reports are deterministic source snapshots, not Gemini-produced
architecture analyses. Each inspects one actual source file, links declarations,
records its Git commit/checksum and states its scope. They are not placeholders,
but neither are they twenty full AI architecture reports. The existing --generate
mode remains available for explicitly running full AI reports with your provider.

A static flow tracer cannot guarantee every runtime call in arbitrary dynamic
programs. The PDF's practical rule is followed: evidence is shown and unproven
links are labelled inferred. This build does not claim complete runtime resolution.

A requirements.txt constraint alone cannot reveal an installed transitive graph.
Use recorded lockfiles/environment exports. Graph edges preserve markers or
unresolved targets rather than pretending a dependency is installed. Advisory
checks remain bounded at 60 packages and source selection remains bounded.

The audit's requested auth migration is implemented as an explicit offline operation,
not an automatic startup data rewrite. Back up first, stop the API, preview, and
apply to an empty destination. SQLite remains the default until you configure both
database URLs. Existing OAuth provider IDs are not merged or regenerated.

## Verification performed on this exact source

- Dependencies installed from requirements.txt, including Authlib and parser packages.
- Full Python suite: **234 passed, 1 skipped**. The skipped test requires a PostgreSQL service.
- Frontend API-client tests: **12 passed**.
- Production Vite build: passed for landing, login, signup, dashboard, gallery and twenty static report pages.
- Live public GitHub gallery evidence: twenty repositories fetched and reports generated.
- Live public GitHub freshness: passed; a deliberately old SHA was flagged stale.
- One existing Authlib deprecation warning remains.

External model calls in automated tests are mocked. Google/GitHub OAuth login,
live Gemini answer quality, real Ollama inference, PostgreSQL server behavior,
browser interaction, PR comment posting, Marketplace publication and hosted
deployment are NOT claimed verified. This environment could not install a
PostgreSQL server because its OS permissions prevented package setup. No Ollama
service is installed. Earlier automatic review blocked sending source evidence to
Gemini using the uploaded credential; that approval has not been bypassed.

.github/workflows/verify.yml now provisions a real PostgreSQL service, runs the
complete backend suite and frontend build/tests, and runs the included Playwright
scenarios. It is authored but has not run on your GitHub repository. No PR comment
was sent to anyone. The public hosted website has not been changed by this ZIP.

## Remaining release gates

1. Run the verification workflow in the actual repository and inspect the real
   PostgreSQL and browser jobs.
2. Test Google/GitHub sign-in with your real configured callback URLs.
3. Run live Gemini and Ollama questions on three repositories and inspect citations,
   retrieval misses/fixes, quota behavior and latency.
4. Exercise the PR workflow on a real authorized PR; inspect the generated comment.
5. Deploy the tested build to the chosen host and verify its production origin.

These are operational acceptance gates, not passing tests disguised as completed
production verification. Do not label the entire product production-ready until
the results exist.
