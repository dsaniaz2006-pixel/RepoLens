"""Display effective RAG performance settings without exposing credentials.

Run from the project root: python scripts/rag_speed_preflight.py
"""
from pathlib import Path
import sys
import os
from dotenv import load_dotenv

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
load_dotenv(root / '.env')
from backend.core.config import (  # noqa: E402  (dotenv must load first)
    RAG_INDEX_PROFILE, RAG_MAX_FILES, RAG_MAX_FILE_CHARS,
    RAG_CONTEXT_BUDGET, CHUNK_SIZE_CHARS, CHUNK_OVERLAP_CHARS,
    EMBEDDING_MODEL,
)


def main():
    print('RepoLens RAG indexing profile:', RAG_INDEX_PROFILE)
    print('Maximum selected files:', RAG_MAX_FILES)
    print('Total source character budget:', f'{RAG_CONTEXT_BUDGET:,}')
    print('Maximum characters per file:', f'{RAG_MAX_FILE_CHARS:,}')
    print('Chunk size / overlap:', CHUNK_SIZE_CHARS, '/', CHUNK_OVERLAP_CHARS)
    print('Embedding model:', EMBEDDING_MODEL)
    print('Local RPM / estimated TPM:',
          os.getenv('REPOLENS_EMBED_RPM', '10'), '/',
          os.getenv('REPOLENS_EMBED_TPM', '20000'))
    print('Estimated UTF-8 bytes/token:', os.getenv('REPOLENS_EMBED_CHARS_PER_TOKEN', '2.0'))
    print('Existing completed indexes are reused only when SHA and settings match.')
    if RAG_INDEX_PROFILE == 'quick':
        print('Coverage: reduced. Change profile to balanced or full for deeper source coverage.')
    print('These are local budgets, not a statement of your Gemini provider quota.')


if __name__ == '__main__':
    main()
