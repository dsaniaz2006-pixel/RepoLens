"""Conservative, evidence-only source symbol discovery for codebase Q&A.

This is *not* a substitute for the model's reasoning: it finds declarations in the
already-retrieved, revision-pinned source. In particular, it cannot infer call
flows or semantics from a name alone. It never reads the filesystem or executes
repository code.
"""
from __future__ import annotations

import re
from pathlib import PurePosixPath

_DECLARATION = re.compile(
    r'^\s*(?:(?:async\s+)?def\s+|(?:export\s+)?(?:async\s+)?function\s+)'
    r'([A-Za-z_$][\w$]*)\s*\(', re.M)
_STOP = {'a', 'an', 'the', 'where', 'which', 'what', 'when', 'why', 'who', 'whose',
         'how', 'does', 'do', 'is', 'are', 'can', 'in', 'from', 'its', 'it', 'of',
         'for', 'to', 'and', 'this', 'that', 'with', 'function', 'method', 'code',
         'source', 'file', 'define', 'defines', 'defined', 'implementation',
         'implement', 'handles', 'handling', 'handle', 'please', 'show',
         'registers', 'register', 'registered', 'on', 'be', 'by', 'used'}
_SOURCE_SUFFIXES = {'.py', '.js', '.jsx', '.ts', '.tsx', '.go', '.rs', '.rb', '.java'}


def tokens(text):
    return set(re.findall(r'[a-z][a-z0-9]*', (text or '').lower()))


def declarations(chunks):
    """Yield (symbol, chunk) only when declaration text exists in supplied evidence."""
    for c in chunks:
        if not isinstance(c, dict) or not all(k in c for k in ('path', 'text', 'start_line', 'end_line')):
            continue
        if PurePosixPath(c['path']).suffix.lower() not in _SOURCE_SUFFIXES:
            continue
        for match in _DECLARATION.finditer(c['text']):
            symbol = match.group(1)
            # Avoid generic non-meaningful methods appearing in all projects.
            if symbol.startswith('__') or symbol in {'init', 'get', 'set', 'run'}:
                continue
            yield symbol, c


def ranked_definitions(question, chunks):
    """Rank direct function definitions; return no match for weak or generic overlap."""
    q=tokens(question) - _STOP
    wanted_exact=set(re.findall(r'`([a-zA-Z_]\w*)`', question))
    results=[]
    for symbol,c in declarations(chunks):
        name=tokens(symbol.replace('_', ' '))
        matched=name & q
        if not matched and symbol not in wanted_exact:
            continue
        # An exact symbol match is stronger than repetitions of the name in docs.
        exact = bool(symbol in wanted_exact or symbol.lower() in q)
        score = len(matched) * 5 + (12 if exact else 0)
        if name and len(matched) == len(name):
            score += 6
        # A bare 'route' definition alone only establishes the location, but
        # decorator behavior is visible if the function's body mentions it.
        body=c['text'].lower()
        if 'decorator' in q and ('decorator' in body or '@' in body):
            score += 4
        if 'dispatch' in q and 'dispatch' in name:
            score += 3
        if score >= 8:
            results.append((score,symbol,c))
    return sorted(results,key=lambda item:(-item[0],item[2]['path'],item[2]['start_line']))


def grounded_definition_answer(question, chunks):
    """Safe partial response when a model omitted citations despite exact definitions.

    Do not assert that a declaration performs a behavior (or links to another)
    without body/call evidence. Return None rather than manufacture an answer.
    """
    found=ranked_definitions(question,chunks)
    if not found:
        return None
    _score,symbol,chunk=found[0]
    source=chunk['path']
    start=chunk['start_line']
    end=chunk['end_line']
    # A declaration alone proves location, not execution flow.
    q=question.lower()
    asks_flow=bool(re.search(r'\b(how|connect|flow|call|interact|why|works|work)\b',q))
    if asks_flow:
        answer=(f'The indexed source defines `{symbol}()` in `{source}`. '
                'This source passage verifies the definition, but a complete '
                'execution-flow explanation needs matching caller/callee evidence.')
    else:
        answer=f'The indexed source defines `{symbol}()` in `{source}` (lines {start}–{end}).'
    return {'answer':answer,'citations':[{'path':source,'start_line':start,'end_line':end}],
            'uncertain':asks_flow}


def grounded_source_answer(question, chunks):
    """Conservative partial flow answer from *actual* declarations and calls.

    Only used if the model supplied no citations. Never invents an edge in an
    execution graph or uses previously generated answers as proof.
    """
    if not re.search(r'\b(how|flow|connect|dispatch|register|handling|handle|explain|detail|revisit)\b',question,re.I):
        return None
    declared=list(declarations(chunks))
    if not declared:
        return None
    q=tokens(question)
    candidates=[]
    for name,c in declared:
        parts=tokens(name)
        if parts & q or (('route' in q or 'routes' in q or 'routing' in q)
                         and parts & {'route','rule','url'}) or (
                         'request' in q or 'handling' in q or 'dispatch' in q) and parts & {'dispatch','request'}:
            if (name,c) not in candidates:
                candidates.append((name,c))
    # A deictic follow-up can omit all relevant symbol names. In that case
    # list independently observed declarations, never assert their relation.
    if len({name for name,_ in candidates})<2 and re.search(
            r'\b(those|these|they|them|second\s+question|question\s+2)\b',question,re.I):
        candidates=list(dict(((name,c['path'],c['start_line']), (name,c)) for name,c in declared).values())
    if len({name for name,_ in candidates})<2:
        return None
    chosen=candidates[:4]
    refs=[]
    sentences=[]
    for name,c in chosen:
        ref={k:c[k] for k in ('path','start_line','end_line')}
        if ref not in refs: refs.append(ref)
        sentences.append(f'`{name}()` is defined in `{c["path"]}`.')
    names={name for name,_ in declared}
    # Mention a call only when the exact symbol appears in a *different*
    # declaration's cited body. Even then, do not infer transitive behavior.
    for caller, c in chosen:
        for callee in names:
            if caller != callee and re.search(r'\b'+re.escape(callee)+r'\s*\(', c['text']):
                sentences.append(f'The cited `{caller}()` passage calls `{callee}()`.')
                break
    sentences.append('The retrieved passages do not by themselves establish every link in the complete execution flow.')
    return {'answer':' '.join(sentences), 'citations':refs, 'uncertain':True}
