# RepoLens: source-grounded chat answer repair (11 November 2026)

## User-reported symptom

RAG indexing finishes, but Flask questions such as "Where does Flask define its route decorator?" and "Which function registers a URL rule?" produce the same generic message: "The retrieved passages did not produce a source-cited answer…". The UI shows that source files were retrieved, so this is **not proof that the index build failed**.

## Confirmed code defects

1. `backend/ai/qa.py` discarded every model answer with an empty `citations` array, replacing it with the same generic message even when the supplied source included a directly verifiable function declaration.
2. `backend/rag/retriever.py` fused BM25 and embedding ranking, but documentation with repeated words could outrank an exact source `def`, hiding useful source in the five-chunk answer window.
3. `contextual_query` did not resolve the phrase "the function from question 2", so follow-up retrieval lacked the referenced question's terminology.
4. In a newly initialized SQLite conversation database, the chat listing could query `workspace_members` before that table had been created.

## Implemented fixes

- `backend/rag/source_symbols.py` (new): extracts explicit source `def`/`function` declarations from **only** pinned-revision, already indexed source chunks. Ranks exact symbol definitions. It does not make claims about a call chain merely from symbol names.
- `backend/rag/retriever.py`: puts verified, question-relevant source declarations ahead of word-heavy documentation when available; all evidence stays scoped to the requested repo and commit. Follow-ups that explicitly name question N include that saved question and answer as search hints, never as evidence.
- `backend/ai/qa.py`: tells the model more clearly to return actual path/line citation objects. When the model does not cite anything, uses a narrow, **source-backed definition answer** if a matching declaration is present. Otherwise makes one evidence-only model retry; cites are still validated strictly against supplied chunks. If nothing supports the claim, it remains uncertain rather than inventing an answer.
- `backend/database/conversations.py`: ensures workspace membership schema exists before an otherwise empty conversation database is queried.
- `tests/test_qa_source_grounding_tdd.py` (new): failing-before/passing-after cases for route decorator, `add_url_rule`, doc-vs-source ranking, question-2 reference, safe abstention, citation-repair retry, and conversation persistence.
- `scripts/qa_index_diagnostics.py` (new): prints indexed path counts and matching source symbols (not source content or credentials) for a given repo/current revision/profile.

## Verified in the coding environment

- Expanded offline Python source/retrieval/conversation regressions: **174 passed, 1 deselected** (the deselected API fixture requires Authlib).
- Frontend Node unit tests: 19 passed (frontend UI unchanged).
- Python compilation: passed.
- Broader tests include hundreds of passes, but full test suite is **not certified here**: `authlib` and some native Tree-sitter parser dependencies are unavailable. Package installation could not reach an external package index.
- Real Gemini and ChromaDB integration have **not been executed here** (no user credentials or local index available).

## Mac verification

Inside the new `RepoLens` folder, restore your existing **private** `.env` and `.repolens_chroma` safely from your working installation (back up both first), then:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
cd frontend
npm ci
npm test
npm run build
npm run test:browser
cd ..
node start.mjs
```

Open **Conversations**, create a **new** chat and ask the four Flask questions. An existing saved generic response remains in history; code updates do not rewrite past conversations. The revised retrieval/ranking does not inherently require re-embedding a complete index if the relevant files are already indexed.

To diagnose coverage, while in the project root with `.venv` active:

```bash
python scripts/qa_index_diagnostics.py https://github.com/pallets/flask --question "Where does Flask define its route decorator?"
python scripts/qa_index_diagnostics.py https://github.com/pallets/flask --question "Which function registers a URL rule?"
python scripts/qa_index_diagnostics.py https://github.com/pallets/flask --question "How does Flask dispatch a request?"
```

If a matching declaration isn't in your **Quick** index, no answerer can reliably explain that absent implementation from that index alone. Set `REPOLENS_RAG_INDEX_PROFILE=balanced` in `.env`, restart the app, rebuild its index, and rerun the diagnostics. Balanced takes more indexing resources but covers more code; it is not needed if the existing index already contains the symbols.

All cited paths and lines must come from the indexed, pinned source. The deterministic fallback identifies only a symbol definition: for complex execution flow, it explicitly states when more caller/callee evidence is needed.
