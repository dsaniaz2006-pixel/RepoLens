"""Retrieve only evidence from the requested repository and immutable revision."""
from backend.core.config import EMBEDDING_MODEL, RAG_TOP_K
from backend.rag.embeddings import embed_texts
from backend.rag.rag_store import query_chunks, read_index_chunks
import re
import math
from collections import Counter
from pathlib import PurePosixPath
from backend.rag.source_symbols import ranked_definitions

def retrieve(repo, revision, question, *, top_k=RAG_TOP_K, embedder=embed_texts, query_fn=query_chunks, lexical_fn=None):
    if not question or not question.strip():
        raise ValueError('Question must not be empty')
    if top_k < 1:
        raise ValueError('top_k must be positive')
    vector = embedder([question], task_type='RETRIEVAL_QUERY')[0]
    candidates = query_fn(repo, revision, EMBEDDING_MODEL, vector, top_k=top_k * 5)
    # Keep explicit paths and identifiers searchable even when embeddings miss them.
    # Custom query adapters remain isolated unless a lexical adapter is supplied.
    if lexical_fn is not None or query_fn is query_chunks:
        all_chunks = (lexical_fn or read_index_chunks)(repo, revision, EMBEDDING_MODEL)
        ranked = lexical_rank(question, all_chunks)
        scores = {}; records = {}
        def key(c): return (c['path'], c['start_line'], c['end_line'])
        for weight, group in [(1, candidates), (1.2, ranked)]:
            for i,c in enumerate(group):
                k=key(c); records[k]=c; scores[k]=scores.get(k,0)+weight/(60+i+1)
        candidates=[records[k] for k in sorted(scores,key=scores.get,reverse=True)]
        # BM25 over documentation can outrank the actual implementation.
        # Promote only declarations that are present verbatim in this revision's
        # indexed source; do not infer paths or fetch other repositories.
        symbols=ranked_definitions(question, all_chunks)
        if symbols:
            priority=[]
            for _,_,c in symbols:
                k=key(c)
                if k not in priority:
                    priority.append(k)
                if len(priority)>=top_k:break
            candidates=[records[k] if k in records else next(c for c in all_chunks if key(c)==k)
                        for k in priority]+[c for c in candidates if key(c) not in priority]
        paths=explicit_paths(question)
        if paths:
            candidates.sort(key=lambda c: c['path'] not in paths)
        candidates = _deep_evidence_order(
            question, all_chunks, candidates, top_k
        )
    # A long README can occupy every nearest-neighbor slot. Keep semantic
    # order while allowing other files into the evidence window. If too few
    # distinct files exist, fill remaining slots from the original ranking.
    chosen=[]; deferred=[]; counts={}
    file_cap = min(top_k, 6) if _deep_targets(question) else 2
    for chunk in candidates:
        path=chunk['path']
        if counts.get(path,0)<(top_k if path in explicit_paths(question) else file_cap) and len(chosen)<top_k:
            chosen.append(chunk);counts[path]=counts.get(path,0)+1
        else:
            deferred.append(chunk)
    return chosen + deferred[:max(0,top_k-len(chosen))]


def explicit_paths(question):
    return set(re.findall(r"[\w.-]+(?:/[\w.-]+)+\.[A-Za-z0-9]+", question))


_STOP = {'the','is','a','of','in','and','to','how','does','what','it','this','that',
         'for','with','from','give','explain','code','source','file','paths','cite',
         'identify','relevant','where','which','function','functions','flask'}
_ALIASES = {
    'routes': {'route','url','rule'}, 'route': {'url','rule'}, 'routing': {'route','url','rule'},
    'register': {'add','rule','map'}, 'registers': {'add','rule','map'},
    'registration': {'register','add','rule'}, 'registered': {'add','rule'},
    'requests': {'request','dispatch'}, 'request': {'dispatch'},
    'handling': {'handle','dispatch'}, 'handle': {'dispatch'},
    'connect': {'call','dispatch'}, 'connection': {'call','dispatch'},
}


def _tokens(text):
    # Splitting snake_case and camelCase is crucial for add_url_rule and
    # dispatchRequest: each part should match natural-language questions.
    text=re.sub(r'([a-z])([A-Z])',r'\1 \2',text or '')
    return re.findall(r'[a-z][a-z0-9]*',text.lower())


def _query_terms(question):
    terms=set(_tokens(question))-_STOP
    for term in tuple(terms):
        terms.update(_ALIASES.get(term,()))
    return terms


def _rank_prepared(question, chunks, docs, lengths):
    terms=_query_terms(question)
    avg=sum(lengths)/max(1,len(docs))
    df={term:sum(term in d for d in docs) for term in terms}
    paths=explicit_paths(question)
    scored=[]
    for chunk,doc,length in zip(chunks,docs,lengths):
        score=0.0
        for term in terms:
            f=doc[term]
            if f:
                score+=math.log(1+(len(docs)-df[term]+.5)/(df[term]+.5))*f*2.2/(f+1.2*(.25+.75*length/max(avg,1)))
        if chunk['path'] in paths:score+=20
        if score>0:
            # Documentation helps orientation but shouldn't displace actual
            # implementation when both contain the same search words.
            if PurePosixPath(chunk['path']).suffix.lower() in {'.py','.js','.ts','.tsx','.jsx','.go','.rs','.java','.rb'}:
                score+=3.0
            scored.append((score,chunk))
    return [chunk for _,chunk in sorted(scored,key=lambda x:x[0],reverse=True)[:30]]


def lexical_rank(question, chunks):
    """BM25-style ranking with source weighting and code-symbol tokenization."""
    docs=[Counter(_tokens(c['text']+' '+c['path'])) for c in chunks]
    return _rank_prepared(question,chunks,docs,[sum(d.values()) for d in docs])


_ORDINALS = {'first':1,'second':2,'third':3,'fourth':4,'fifth':5,
             'sixth':6,'seventh':7,'eighth':8,'ninth':9,'tenth':10}


def referenced_question_number(question):
    """Resolve natural references without re-numbering a truncated chat window."""
    match=re.search(r'\b(?:from|in|of|about|on|for|at|see|refer(?:ring)?\s+to|the|explain|answer\s+to)\s+(?:the\s+)?question\s*(?:number\s*)?(\d+)\b',question,re.I)
    if match:return int(match.group(1))
    match=re.search(r'\b('+'|'.join(_ORDINALS)+r')\s+question\b',question,re.I)
    if match:return _ORDINALS[match.group(1).lower()]
    return None


def contextual_query(question, history, *, referenced_turn=...):
    # Standalone questions with explicit source paths must not inherit topics.
    if explicit_paths(question):
        return question
    ordinal=referenced_question_number(question)
    users=[m.get('content','')[:800] for m in history if m.get('role')=='user']
    if ordinal is not None:
        if referenced_turn is not ...:
            if not referenced_turn:
                return question
            user, assistant=referenced_turn
            if user.get('role')!='user' or assistant.get('role')!='assistant':
                return question
            # A referenced question can itself contain "those functions".
            # Carry antecedents from the recent window when available; long
            # histories may also be augmented by the caller's DB lookup.
            earlier=[q for q in users if q != user.get('content','')][:2]
            return (question+'\nReferenced question: '+user.get('content','')[:800]
                    +'\nEarlier context: '+' | '.join(earlier)
                    +'\nEarlier answer: '+assistant.get('content','')[:250])
        position=ordinal-1
        if 0<=position<len(users):
            context=' | '.join(users[max(0,position-2):position])
            count=0
            prior_answer=''
            for i,msg in enumerate(history):
                if msg.get('role')=='user':
                    count+=1
                    if count==ordinal:
                        prior_answer=next((a.get('content','')[:300] for a in history[i+1:]
                                           if a.get('role')=='assistant'),'')
                        break
            return (question+'\nReferenced question: '+users[position]
                    +('\nEarlier context: '+context if context else '')
                    +('\nEarlier answer: '+prior_answer if prior_answer else ''))
        return question
    if not re.search(r'\b(it|its|they|them|those|that|these|this|same)\b',question,re.I):
        return question
    earlier=users[-2:]
    label='Previous question: ' if len(earlier)==1 else 'Previous questions: '
    return question + ('\n'+label+' | '.join(earlier) if earlier else '')


# Deep RAG: prioritize evidence already stored in the pinned index.
def _deep_targets(question):
    names = list(dict.fromkeys(re.findall(
        r"\b[a-zA-Z][a-zA-Z0-9]*(?:_[a-zA-Z0-9]+)+\b",
        question
    )))

    if re.search(
        r"\b(?:trace.{0,45}request|request.{0,25}flow|lifecycle)\b",
        question, re.I
    ):
        for name in (
            "full_dispatch_request", "preprocess_request",
            "dispatch_request", "finalize_request", "match_request"
        ):
            if name not in names:
                names.append(name)

    return names[:8]


def _deep_evidence_order(question, indexed, ranked, top_k):
    names = _deep_targets(question)

    if not names:
        return ranked

    chosen, seen = [], set()

    def key(c):
        return (c["path"], c["start_line"], c["end_line"])

    def add(c):
        if key(c) not in seen:
            chosen.append(c)
            seen.add(key(c))

    paths = explicit_paths(question)

    for name in names:
        hits = []

        for c in indexed:
            suffix = PurePosixPath(c["path"]).suffix.lower()

            if suffix not in (
                ".py", ".js", ".ts", ".tsx",
                ".jsx", ".go", ".rs", ".java"
            ):
                continue

            body = c["text"]
            pattern = r"\b" + re.escape(name) + r"\b"

            if not re.search(pattern, body):
                continue

            score = 1 + (20 if c["path"] in paths else 0)

            if re.search(
                r"\b(?:def|function)\s+" +
                re.escape(name) + r"\s*\(",
                body
            ):
                score += 7

            if re.search(
                pattern + r"\s*(?:\[[^\n]{1,80}\])?\s*=|" +
                pattern + r"\.add\s*\(",
                body
            ):
                score += 12

            if re.search(
                r"\bself\." + re.escape(name) +
                r"\s*(?:\(|\[|\.)",
                body
            ):
                score += 6

            if "NotImplementedError" in body:
                score -= 12

            hits.append((score, c))

        if hits:
            add(max(hits, key=lambda item: item[0])[1])

        if len(chosen) >= top_k:
            break

    # Include adjacent indexed chunks when they really touch.
    # Never bridge missing source lines or invent evidence.
    for seed in chosen[:]:
        if len(chosen) >= top_k:
            break

        neighbors = [
            c for c in indexed
            if c["path"] == seed["path"]
            and key(c) not in seen
            and (
                0 <= c["start_line"] - seed["end_line"] <= 1
                or 0 <= seed["start_line"] - c["end_line"] <= 1
            )
        ]

        if neighbors:
            add(min(
                neighbors,
                key=lambda c: abs(
                    c["start_line"] - seed["end_line"]
                )
            ))

    return chosen + [
        c for c in ranked if key(c) not in seen
    ]
