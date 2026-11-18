"""Shared CLI/API pipeline; never execute or clone untrusted repository code."""
from backend.github.github_client import parse_github_url, fetch_repo_metadata, fetch_tree, fetch_commit_sha, collect_selected_file_contents
from backend.services.file_selector import filter_and_rank, rank_for_rag_index
from backend.ai.analyzer import analyze_repository
from backend.services.report import save_report
from backend.rag.chunker import chunk_files
from backend.rag.embeddings import embed_texts
from backend.rag.rag_store import store_chunks, get_collection, collection_name, StoreError
from backend.core.config import (EMBEDDING_MODEL, RAG_MAX_FILES, RAG_MAX_FILE_CHARS, RAG_CONTEXT_BUDGET,
                    CHROMA_PATH, INDEX_FORMAT_VERSION, CHUNK_SIZE_CHARS, CHUNK_OVERLAP_CHARS, RAG_INDEX_PROFILE, RAG_INDEX_EFFECTIVE_BUDGET)
import json
import time
from backend.core.operation_progress import report_progress
from pathlib import Path
from threading import Lock
from backend.rag.retriever import retrieve
from backend.ai.qa import answer_question

_index_locks = {}
_index_locks_guard = Lock()


def collect_repo(url, *, pin_revision=False, revision=None, for_index=False):
    owner, repo = parse_github_url(url)
    report_progress("Fetching GitHub repository metadata…")
    metadata = fetch_repo_metadata(owner,repo)
    if metadata.get('private'): raise ValueError('Only public repositories are supported')
    if revision is not None and (len(revision) != 40 or any(c not in '0123456789abcdefABCDEF' for c in revision)):
        raise ValueError('Revision must be a full 40-character Git commit SHA')
    revision = revision or (fetch_commit_sha(owner,repo,metadata['default_branch']) if pin_revision else metadata['default_branch'])
    report_progress("Fetching repository tree…")
    tree, truncated = fetch_tree(owner,repo,revision)
    report_progress("Downloading selected source files from GitHub…")
    if for_index:
        selected = rank_for_rag_index(tree, limit=RAG_MAX_FILES)
        records = collect_selected_file_contents(owner,repo,revision,selected,tree,
            max_files=RAG_MAX_FILES,max_file_chars=RAG_MAX_FILE_CHARS,total_budget=RAG_INDEX_EFFECTIVE_BUDGET,fetch_workers=4,
            index_excerpts=(RAG_INDEX_PROFILE == "quick"))
    else:
        selected = filter_and_rank(tree)
        records = collect_selected_file_contents(owner,repo,revision,selected,tree)
    usable = [r for r in records if not r.get('skipped') and r.get('content')]
    if not usable:
        raise ValueError('No safe source files were available for analysis')
    return dict(owner=owner, repo=repo, metadata=metadata, revision=revision,
                tree=tree, truncated=truncated, records=usable, repo_id=f'{owner}/{repo}'.lower())


def generate_report(url, *, output_dir='reports', overwrite=False, capture_evidence=False):
    data = collect_repo(url,pin_revision=True)
    report_progress('Analyzing selected source with AI…')
    analysis = analyze_repository(data['metadata'],data['tree'],data['records'],data['truncated'])
    report_progress('Saving verified analysis report…')
    path = save_report(analysis,data['metadata'],data['tree'],data['owner'],data['repo'],
                       output_dir=output_dir, overwrite=overwrite, tree_truncated=data['truncated'])
    from backend.services.code_flow import trace, markdown
    report_progress('Tracing code flow and finalizing report…')
    flow=trace(data['records'])
    analysis['verified_flow']=flow
    with path.open('a',encoding='utf-8') as output: output.write(markdown(flow))
    if capture_evidence:
        import json
        path.with_suffix('.evidence.json').write_text(json.dumps({
            'repository':data['repo_id'], 'revision':data['revision'],
            'analysis':analysis, 'records':data['records'],
            'metadata':data['metadata'], 'tree':data['tree'],
        },indent=2),encoding='utf-8')
    return {'analysis':analysis,'metadata':data['metadata'],'report_path':str(path),
            'tree':data['tree'],'truncated':data['truncated'], 'revision':data['revision'],
            'evidence_paths':[r['path'] for r in data['records']]}


def index_settings():
    return dict(model=EMBEDDING_MODEL,format=INDEX_FORMAT_VERSION,chunk_size=CHUNK_SIZE_CHARS,
        overlap=CHUNK_OVERLAP_CHARS,max_files=RAG_MAX_FILES,max_file_chars=RAG_MAX_FILE_CHARS,
        budget=RAG_CONTEXT_BUDGET,effective_budget=RAG_INDEX_EFFECTIVE_BUDGET,profile=RAG_INDEX_PROFILE)


def record_completed_index(result):
    name=collection_name(result['repository'],result['revision'],EMBEDDING_MODEL)
    path=Path(CHROMA_PATH)/'completed'/f'{name}.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(dict(result=result,settings=index_settings()),indent=2))
    temporary.replace(path)


def resume_completed_index(repo,revision):
    name=collection_name(repo,revision,EMBEDDING_MODEL)
    path=Path(CHROMA_PATH)/'completed'/f'{name}.json'
    if not path.exists():return None
    try:
        saved=json.loads(path.read_text())
        if saved['settings']!=index_settings():return None
        result=saved['result']
        if result['repository']!=repo or result['revision']!=revision:return None
        col=get_collection(repo,revision,EMBEDDING_MODEL)
        if isinstance(col.metadata, dict) and col.metadata.get('repolens_complete') is False:
            return None
        metadata=col.get(include=['metadatas'])['metadatas']
        if col.count()!=result['chunks'] or not metadata:return None
        if any(m['repo']!=repo or m['revision']!=revision for m in metadata):return None
        if len({m['path'] for m in metadata})!=result['indexed_files']:return None
        return dict(result,resumed=True)
    except (KeyError,TypeError,ValueError,OSError,StoreError):
        return None
    except Exception as exc:
        raise StoreError('Unable to validate the saved index checkpoint') from exc


def index_repo(url, *, revision=None, resume=False):
    # The legacy synchronous API also enters here. Guard it alongside jobs so
    # two requests cannot overwrite the same checkpoint or collection.
    owner, repo = parse_github_url(url)
    key = f'{owner}/{repo}'.lower()
    with _index_locks_guard:
        lock = _index_locks.setdefault(key, Lock())
    if not lock.acquire(blocking=False):
        raise ValueError('This repository is currently being indexed. Please retry shortly.')
    try:
        return _index_repo(url, revision=revision, resume=resume)
    finally:
        lock.release()


def _index_repo(url, *, revision=None, resume=False):
    if resume and revision:
        owner,repo=parse_github_url(url)
        existing=resume_completed_index(f'{owner}/{repo}'.lower(),revision)
        if existing:return existing
    started = time.monotonic()
    if revision is None:
        # A completed index is immutable for its Git SHA and exact index settings.
        # Avoid downloading/re-embedding the entire repository on repeated clicks.
        owner, repo = parse_github_url(url)
        metadata = fetch_repo_metadata(owner, repo)
        if metadata.get('private'):
            raise ValueError('Only public repositories are supported')
        revision = fetch_commit_sha(owner, repo, metadata['default_branch'])
        existing = resume_completed_index(f'{owner}/{repo}'.lower(), revision)
        if existing:
            report_progress('This commit is already indexed; reused the completed index without embedding calls.')
            return dict(existing, reused=True, resumed=True,
                        reuse_lookup_seconds=round(time.monotonic()-started, 2))
    data = collect_repo(url,pin_revision=True,revision=revision,for_index=True)
    fetched_at = time.monotonic()
    report_progress(f"Fetched {len(data['records'])} files in {fetched_at-started:.1f}s. "
                    f'Building {RAG_INDEX_PROFILE} index…')
    chunks = chunk_files(data['records'],data['repo_id'],data['revision'])
    chunked_at = time.monotonic()
    report_progress(f'Embedding {len(chunks)} source chunks ({RAG_INDEX_PROFILE} coverage; line-accurate source excerpts)…')
    name=collection_name(data['repo_id'],data['revision'],EMBEDDING_MODEL)
    vectors = embed_texts([f"File: {c['path']}\n{c['text']}" for c in chunks],
        checkpoint_path=Path(CHROMA_PATH)/'embedding-checkpoints'/f'{name}.json')
    embedded_at = time.monotonic()
    report_progress('Saving vectors to the local index…')
    count = store_chunks(data['repo_id'],data['revision'],EMBEDDING_MODEL,chunks,vectors)
    stored_at = time.monotonic()
    result={'repository':data['repo_id'],'revision':data['revision'],'chunks':count,
            'indexed_files':len(set(c['path'] for c in chunks)),'tree_incomplete':data['truncated'],
            'default_branch':data['metadata'].get('default_branch'),
            'index_profile':RAG_INDEX_PROFILE,
            'build_seconds':round(stored_at-started, 2),
            'timings_seconds':{
                'fetch':round(fetched_at-started, 2),
                'chunk':round(chunked_at-fetched_at, 2),
                'embedding':round(embedded_at-chunked_at, 2),
                'vector_storage':round(stored_at-embedded_at, 2),
            }, 'embedded_characters':sum(len(c['text']) for c in chunks)}
    report_progress(f'Finalizing completed index after {time.monotonic()-started:.1f}s…')
    record_completed_index(result)
    return result


def ask_repo(url, question, *, conversation_id=None, user_id=None, store=None, version=None):
    # Reject invalid questions before fetching metadata, spending GitHub quota,
    # or creating a conversation turn. The retriever still validates again.
    if not isinstance(question, str) or not question.strip():
        raise ValueError('Question must not be empty')
    if conversation_id:
        if not user_id or store is None: raise ValueError("Authenticated conversation storage is required")
        from backend.database.conversations import answer_turn
        return answer_turn(store,user_id,conversation_id,url,question,version)
    owner,repo = parse_github_url(url)
    metadata = fetch_repo_metadata(owner,repo)
    if metadata.get('private'): raise ValueError('Only public repositories are supported')
    revision = fetch_commit_sha(owner,repo,metadata['default_branch'])
    chunks = retrieve(f'{owner}/{repo}'.lower(),revision,question)
    result = answer_question(question,chunks)
    return {'repository':f'{owner}/{repo}','revision':revision, **result}
