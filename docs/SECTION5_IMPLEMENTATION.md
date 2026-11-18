# RepoLens Section 5 — Conversational Codebase Chat

## Scope

This is a focused upgrade of the existing Section 4 application, not a replacement
of the database, auth, UI, RAG index, or AI models. It does not add an Alembic migration.

### Changes

- `backend/database/conversations.py`: resolves numbered references from the persisted
  conversation by absolute message position. Access uses the same owner and workspace
  membership checks as normal conversation reads. The historical turn is inserted into
  a bounded 12-message context only when missing from the usual recent window.
- `backend/rag/retriever.py`: accepts an explicitly verified referenced turn instead
  of renumbering the last six user questions as though they were the conversation start.
  Standalone questions and questions without resolvable references do not inherit an
  arbitrary prior topic.
- `frontend/src/features/conversations/Conversations.jsx`: shows question numbers in the current chat and
  constructs source links through a validated helper.
- `frontend/src/features/conversations/conversationDisplay.mjs`: checks repository/revision/citation validity
  before creating a GitHub blob link; always pins the link to the saved commit SHA.

### Intentional unchanged behavior

- Existing `conversations` and `conversation_messages` tables and their contents.
- Browser authentication and CSRF; owner-scoped saved conversation routes.
- Team workspace membership checks.
- ChromaDB indexing, embedding providers, and Gemini configuration.
- Section 4 daily quota enforcement for `/api/ask`.
- Save/restore of conversations and message citations.

### Security notes

All quote/history material remains untrusted context, never repository evidence.
Repository source is still validated by the existing Q&A citation checker.
The historical reference is fetched only from the logged-in owner's chat.

### Limitations and release gates

- Real Gemini responses and ChromaDB retrieval must be verified using an indexed repo
  on the user's Mac.
- Real PostgreSQL E2E should be run on a disposable Neon test branch with
  `REPOLENS_TEST_POSTGRES_URL`; do not point the test at production.
- The Playwright browser test was authored, but could not run in the offline build
  environment because Vite/React/npm dependencies could not be installed.
- Existing code-flow and public gallery tests have four failures reproduced in
  the untouched Section 4 source; they are outside this section's changes.
