"""Allowlisted local snapshots. Never invokes Git, hooks, shells or cloud providers."""
import hashlib,json,os,re,stat
from pathlib import Path
from backend.ai.model_provider import provider
from backend.core.config import SKIP_DIR_NAMES,RAG_MAX_FILES,RAG_MAX_FILE_CHARS,RAG_CONTEXT_BUDGET
from backend.services.file_selector import filter_and_rank
from backend.github.github_client import _looks_like_secret_content


def require_local():
    from backend.core.config import EMBEDDING_MODEL
    if provider()!='ollama' or not EMBEDDING_MODEL.startswith('ollama:'):
        raise ValueError('Local repositories require REPOLENS_MODEL_PROVIDER=ollama at server startup; restart after changing it')


def approved(user):
    require_local()
    try:config=json.loads(os.getenv('REPOLENS_LOCAL_REPOSITORIES','{}'))
    except ValueError:raise ValueError('Invalid local repository configuration')
    if not isinstance(config,dict):raise ValueError('Local repositories must be an alias mapping')
    result={}
    for alias,value in config.items():
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',alias) or not isinstance(value,dict):continue
        # Explicit users prevent a newly registered OAuth user from reading private code.
        users=value.get('users')
        if (isinstance(users,list) and all(isinstance(u,str) for u in users)
                and user in users and isinstance(value.get('path'),str)):
            result[alias]=value['path']
    return result


def collect(alias,user):
    roots=approved(user)
    if alias not in roots:raise ValueError('Local repository is not approved for this account')
    root=Path(roots[alias]).expanduser()
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():raise ValueError('Configured repository must be an absolute, regular directory')
    records=[];limits=[];visited=0;used=0
    # Descriptor-relative traversal and O_NOFOLLOW stop path/symlink substitution.
    rootfd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        for folder,dirs,files,fd in os.fwalk('.',dir_fd=rootfd,follow_symlinks=False):
            dirs[:]=sorted(d for d in dirs if d not in SKIP_DIR_NAMES and not d.startswith('.'))
            for name in sorted(files):
                visited+=1
                if visited>20000:break
                relative=(Path(folder)/name).as_posix().removeprefix('./')
                if name.startswith('.') or any(w in name.lower() for w in ('secret','credential','token','password','id_rsa','id_ed25519')):continue
                if not filter_and_rank([{'path':relative,'type':'blob','size':0}],limit=1):continue
                handle=None
                try:
                    handle=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
                    info=os.fstat(handle)
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:continue
                    if info.st_size>RAG_MAX_FILE_CHARS:
                        limits.append(relative+': exceeds file byte limit');continue
                    with os.fdopen(handle,'rb') as stream:
                        handle=None;raw=stream.read(RAG_MAX_FILE_CHARS+1)
                    if len(raw)>RAG_MAX_FILE_CHARS or b'\0' in raw:continue
                    content=raw.decode('utf-8')
                    if _looks_like_secret_content(content):continue
                    if len(records)>=RAG_MAX_FILES or used+len(content)>RAG_CONTEXT_BUDGET:
                        limits.append('Source selection reached file/context limit');continue
                    records.append({'path':relative,'content':content});used+=len(content)
                except (OSError,UnicodeError):limits.append(relative+': unreadable or unsafe file skipped')
                finally:
                    if handle is not None:os.close(handle)
            if visited>20000:
                limits.append('Directory traversal capped at 20000 files');break
    finally:os.close(rootfd)
    if not records:raise ValueError('No safe readable source files in this repository')
    records.sort(key=lambda x:x['path'])
    revision=hashlib.sha256(json.dumps(records,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    identity=hashlib.sha256((user+'\0'+alias+'\0'+str(root.resolve())).encode()).hexdigest()[:24]
    return {'repo_id':'local/'+identity,'revision':revision,'alias':alias,'records':records,
            'limits':sorted(set(limits))+['Snapshot identifies selected safe file contents, not a Git commit or an atomic filesystem snapshot.'],
            'truncated':bool(limits)}


def _index(alias,user):
    require_local()
    from backend.rag.chunker import chunk_files
    from backend.rag.embeddings import embed_texts
    from backend.rag.rag_store import store_chunks,collection_name
    from backend.services.pipeline import record_completed_index,resume_completed_index
    from backend.core.config import EMBEDDING_MODEL,CHROMA_PATH
    data=collect(alias,user)
    previous=resume_completed_index(data['repo_id'],data['revision'])
    if previous:return dict(previous,alias=alias,limits=data['limits'])
    chunks=chunk_files(data['records'],data['repo_id'],data['revision'])
    name=collection_name(data['repo_id'],data['revision'],EMBEDDING_MODEL)
    vectors=embed_texts([f"File: {c['path']}\n{c['text']}" for c in chunks],checkpoint_path=Path(CHROMA_PATH)/'embedding-checkpoints'/f'{name}.json')
    count=store_chunks(data['repo_id'],data['revision'],EMBEDDING_MODEL,chunks,vectors)
    result={'repository':data['repo_id'],'revision':data['revision'],'chunks':count,'indexed_files':len(data['records']),'tree_incomplete':data['truncated'],'alias':alias,'limits':data['limits']}
    record_completed_index(result)
    return result


def ask(data,user,question):
    require_local()
    # Recheck directory authorization on every request, including old snapshots.
    roots=approved(user)
    if data['alias'] not in roots:raise ValueError('Local repository access was revoked')
    identity=hashlib.sha256((user+'\0'+data['alias']+'\0'+str(Path(roots[data['alias']]).expanduser().resolve())).encode()).hexdigest()[:24]
    if data['repository']!='local/'+identity:raise ValueError('Repository configuration changed; re-index it')
    from backend.rag.retriever import retrieve
    from backend.ai.qa import answer_question
    result=answer_question(question,retrieve(data['repository'],data['revision'],question))
    return dict(result,repository=data['repository'],revision=data['revision'],citation_type='local_path')


def index(alias,user):
    from backend.services.pipeline import _index_locks,_index_locks_guard
    from threading import Lock
    with _index_locks_guard:lock=_index_locks.setdefault(('local',user,alias),Lock())
    if not lock.acquire(blocking=False):raise ValueError('This local repository is currently being indexed')
    try:return _index(alias,user)
    finally:lock.release()
