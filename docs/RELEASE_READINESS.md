# Current delivery

See [RELEASE_2026_10_25.md](./RELEASE_2026_10_25.md) for the authoritative implementation matrix, current test evidence, and exact remaining live steps.

---

## Historical notes (superseded)

# Release candidate status — 2026-10-21

This update is based on the uploaded RepoLens_Clean.zip and the supplied audit/PDF.
It preserves public checklist sharing and the existing authentication, conversation,
workspace, scanner, onboarding and multi-language flow implementations.

## Changes in this update

| Area | Implemented change | Verification boundary |
| --- | --- | --- |
| Startup | Preflight for both ports; explicit backend-port override; matching frontend proxy; no termination of an existing listener | Three launcher regressions passed |
| Freshness | Independent worker and macOS schedule generator; persistent due/error state; shared database lease; deduplicated repository reads; concurrent re-index protection | Worker overlap, restart/due state and re-index race regressions passed; no real schedule installed |
| PR/diff | Existing selector scores; multiple bounded evidence batches; pinned comparison refs; explicit coverage/omitted paths; each batch's citations validated independently | Regression tests; no live model PR analysis or comment posted in this run |
| Gallery | Resumable full AI generation; per-repository failure isolation; staged source review; checksum-bound approval/publication; clear public report types | Stub-provider lifecycle regression; bundled twenty examples remain source snapshots |
| Embeddings | Reject incomplete, non-finite and inconsistent vector batches before caching any batch entries | Invalid-response regressions passed |
| Flow view | Draw actual caller/callee edges, including branches, disconnected components and recursion; remove invented display-order connections | Graph geometry/connectivity frontend regressions passed |
| Migration | Preserve checklist sharing; reset runtime worker leases when copying a database | SQLite migration regressions; real PostgreSQL test remains service-gated |
| Release | Empty credential template; exclude environments, accounts, databases, backups, private staging and reports from release ZIP; preserve public reports | Archive privacy/asset regression and archive integrity validation |
| Operations | Local Ollama probe and detailed FINISH_SETUP.md acceptance guide | Live credential/service checks remain for your environment |

## Fresh verification

- Python: **252 passed, 1 skipped**. The skipped test requires a real dedicated PostgreSQL database.
- Frontend: **17 passed** (API client, progress/error handling and launcher behavior).
- Production Vite build: passed.
- No real Gemini/Ollama inference, OAuth consent flow, PostgreSQL server, CI browser run,
  hosted deployment or PR comment was executed in this update.

The bundled source-receipt checks prove hashes, SHAs and page consistency. Earlier
live-evaluation records, where present, describe their own runs and settings; they
do not establish this release's production readiness or complete all manual gates.
Read FINISH_SETUP.md for exact commands and expected results for each outstanding gate.

## Scope boundaries

The PDF's full reviewed AI gallery still needs model generation and human source
review. Team invitations use single-use tokens. Python/Go transitive graphs require
resolved lockfiles or trusted exports. Static tracing handles supported syntax and
marks inferred/unresolved calls; it cannot promise complete dynamic runtime behavior.
Freshness scheduling needs an awake machine or always-on host. Large PR analysis
remains bounded by configured budgets and GitHub's file/patch limits. No email/push
notification service or hosted credentials are included.

The application has implemented features with automated regression coverage. Full
end-to-end production readiness remains pending the real-service acceptance checks.
