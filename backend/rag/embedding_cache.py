"""Persistent embedding reuse and conservative cross-process request budgets."""
import hashlib,json,os,sqlite3,time,math
from pathlib import Path
from contextlib import contextmanager
from backend.core.operation_progress import pause,report_progress

@contextmanager
def connect():
    directory=Path(os.getenv('REPOLENS_EMBED_CACHE_DIR','.repolens_cache'));directory.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(directory/'embeddings.sqlite3',timeout=30)
    conn.execute('CREATE TABLE IF NOT EXISTS vectors (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS usage (stamp REAL NOT NULL, tokens INTEGER NOT NULL)')
    try:
        with conn: yield conn
    finally: conn.close()

def key(model,task,text):return hashlib.sha256(json.dumps([model,task,'explicit-content-code-retrieval-v1',text]).encode()).hexdigest()
def valid_vector(vector):
    return isinstance(vector,list) and bool(vector) and all(type(x) in (int,float) and math.isfinite(x) for x in vector)
def get(model,task,text):
    with connect() as c:row=c.execute('SELECT value FROM vectors WHERE key=?',(key(model,task,text),)).fetchone()
    if not row:return None
    try:vector=json.loads(row[0])
    except (ValueError,TypeError):return None
    return vector if valid_vector(vector) else None

def put(model,task,text,vector):
    with connect() as c:c.execute('INSERT OR REPLACE INTO vectors VALUES (?,?)',(key(model,task,text),json.dumps(vector)))

def estimate_tokens(text, *, overhead=48):
    """Heuristic estimate, not an exact count or an upper bound on tokens.

    The old limiter charged one token per UTF-8 byte, often 2–4 times actual
    code token use. Charging estimated tokens gives the local rate budget the
    same units as the Gemini quota. 429 responses still take precedence.
    """
    chars_per_token = float(os.getenv('REPOLENS_EMBED_CHARS_PER_TOKEN', '2.0'))
    if not math.isfinite(chars_per_token) or not 1 <= chars_per_token <= 4:
        raise ValueError('REPOLENS_EMBED_CHARS_PER_TOKEN must be between 1 and 4')
    return math.ceil(len(text.encode('utf-8')) / chars_per_token) + overhead


def get_many(model, task, texts):
    """Fetch cached vectors with one SQLite connection, avoiding N opens."""
    if not texts:
        return {}
    keys = {key(model, task, t): t for t in texts}
    found = {}
    with connect() as connection:
        hashes = list(keys)
        for start in range(0, len(hashes), 400):
            batch = hashes[start:start + 400]
            placeholders = ','.join('?' for _ in batch)
            for identity, payload in connection.execute(
                    f'SELECT key, value FROM vectors WHERE key IN ({placeholders})', batch):
                try:
                    vector = json.loads(payload)
                except (TypeError, ValueError):
                    continue
                if valid_vector(vector):
                    found[keys[identity]] = vector
    return found


def put_many(model, task, pairs):
    """Commit each provider batch atomically for reliable restart recovery."""
    if not pairs:
        return
    if any(not valid_vector(vector) for _, vector in pairs):
        raise ValueError('Cannot cache an invalid embedding vector')
    with connect() as connection:
        connection.executemany('INSERT OR REPLACE INTO vectors VALUES (?,?)',
                               ((key(model, task, text), json.dumps(vector))
                                for text, vector in pairs))

class QuotaBudgetError(ValueError):
    """A local limiter cannot make progress safely; cached vectors are retained."""

def reserve(tokens):
    rpm=max(1,int(os.getenv('REPOLENS_EMBED_RPM','10')));tpm=max(1,int(os.getenv('REPOLENS_EMBED_TPM','20000')))
    if tokens>tpm:raise QuotaBudgetError(f'Embedding batch needs {tokens:,} estimated tokens but the local per-minute budget is {tpm:,}. Reduce the batch/chunk size.')
    started=time.monotonic()
    while True:
        report_progress(None)
        now=time.time()
        with connect() as c:
            c.execute('BEGIN IMMEDIATE');c.execute('DELETE FROM usage WHERE stamp<=?',(now-60,))
            rows=c.execute('SELECT stamp,tokens FROM usage ORDER BY stamp').fetchall()
            if any(stamp>now+1 for stamp,_ in rows):
                raise QuotaBudgetError('Local quota timestamps are ahead of the system clock. Check automatic date/time, restart RepoLens, and retry. Saved embeddings are retained.')
            count=len(rows);total=sum(cost for _,cost in rows)
            if count<rpm and total+tokens<=tpm:
                c.execute('INSERT INTO usage VALUES (?,?)',(now,tokens));return
            # Predict when enough reservations expire for this particular batch.
            remaining_count,remaining_tokens=count,total
            wait=1.0
            for stamp,cost in rows:
                remaining_count-=1;remaining_tokens-=cost
                if remaining_count<rpm and remaining_tokens+tokens<=tpm:
                    wait=max(0.1,stamp+60-now+0.1);break
        elapsed=time.monotonic()-started
        if elapsed>=90:
            raise QuotaBudgetError('Local embedding quota stayed busy for 90 seconds. Stop other indexing jobs and retry. Completed batches are cached; no cache deletion is needed.')
        report_progress(f'Local embedding budget: {count}/{rpm} requests, {total:,}/{tpm:,} estimated tokens used. Next batch in about {math.ceil(wait)}s; waited {int(elapsed)}s. This is a local limit, not a Gemini quota response.')
        pause(min(wait,5,90-elapsed))

def cached_embeddings(texts,task,model,generate):
    results=[None]*len(texts);missing={}
    stored=get_many(model,task,texts)
    for i,text in enumerate(texts):
        value=stored.get(text)
        if value is not None:results[i]=value
        else:missing.setdefault(text,[]).append(i)
    completed=sum(value is not None for value in results)
    report_progress(f'Embedding progress: {completed}/{len(texts)} chunks cached; {len(missing)} unique chunks to generate…')
    # Leave headroom for JSON/request framing so a batch fits the local TPM.
    batch=[];used=0;budget=max(1,min(12000,int(os.getenv('REPOLENS_EMBED_TPM','20000'))*0.65))
    def flush():
        nonlocal completed
        if not batch:return
        report_progress(f'Embedding progress: {completed}/{len(texts)} chunks ready; preparing {len(batch)} unique chunks…')
        # UTF-8 bytes plus instruction overhead is a conservative token upper bound.
        vectors=generate(list(batch))
        if not isinstance(vectors,list) or len(vectors)!=len(batch) or not all(valid_vector(v) for v in vectors):
            raise ValueError('Embedding provider returned an incomplete or invalid batch; no vectors from this batch were cached')
        dimensions={len(v) for v in results if v is not None}|{len(v) for v in vectors}
        if len(dimensions)!=1:raise ValueError('Embedding dimensions changed; use a new model-specific cache and rebuild the index')
        put_many(model,task,list(zip(batch,vectors)))
        for text,vector in zip(batch,vectors):
            for i in missing[text]:results[i]=vector
            completed+=len(missing[text])
        report_progress(f'Embedding progress: {completed}/{len(texts)} chunks ready and saved for retry…')
    for text in missing:
        cost=estimate_tokens(text)
        if cost>budget:raise ValueError('Embedding input exceeds batch budget; reduce chunk size')
        if batch and (used+cost>budget or len(batch)>=32):flush();batch=[];used=0
        batch.append(text);used+=cost
    flush()
    # Guard fully-cached resumes too: otherwise an old corrupt vector can
    # escape validation without ever invoking generate().
    if any(not valid_vector(value) for value in results) or len({len(value) for value in results}) > 1:
        raise ValueError('Cached embedding dimensions are inconsistent or vectors are missing; rebuild the affected embedding cache')
    return results
