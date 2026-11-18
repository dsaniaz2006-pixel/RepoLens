# Workspace update — 19 October 2026

## Install into your existing local project

1. Stop RepoLens with Control+C in its running terminal(s).
2. Keep a backup of your current project folder.
3. Extract this ZIP. Copy its updated source files and folders into your existing RepoLens project, merging folders and replacing matching source files. Preserve your existing `.env`, `.venv`, `reports`, `.repolens_auth`, and `.repolens_chroma` folders. The ZIP excludes these private/local files.
4. In the existing project root (in the project root (alongside requirements.txt)), update installed dependencies:

   ```bash
   .venv/bin/python -m pip install -r requirements.txt
   cd frontend
   npm ci
   cd ..
   node start.mjs
   ```

Your existing virtual environment can be reused when updating the same project in place. If you choose a fresh project folder instead, follow README setup and copy your existing `.env` into that folder. Keep the matching OAuth client IDs/secrets and Gemini key; do not replace real values with `.env.example` placeholders.

5. Open http://127.0.0.1:5173/dashboard/ and sign in. Refresh the page after updating. If the favicon is cached, close the old tab and open a new one.

## Check the updated workflow

- Home shows your overview and recent analyses; Analyze Repo opens the analysis workbench.
- The dashboard no longer has a Landing page button. The public landing page remains available before sign-in.
- The same green code logo appears on landing, login, signup, and workspace pages and their browser tabs.
- Analyze a public repository, then open Ask RepoLens and build its RAG index. Read the indexing status and any provider error before asking a question.
- Generate interview questions and a contribution candidate from their report tabs; reopen a saved report from Past Analyses; download Markdown/PDF.

Google/GitHub OAuth credentials authenticate users. `GEMINI_API_KEY` separately enables analysis, embeddings, and Q&A. A successful Google login does not provide Gemini API access or quota.

This update targets the local Python/React project shown in your screenshots. The previously published static website does not host this Python backend.
