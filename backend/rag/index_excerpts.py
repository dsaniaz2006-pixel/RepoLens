"""Fast, line-accurate excerpts for *indexing* large source files.

A Quick index cannot contain every byte of a large repository. Rather than
blindly keeping the beginning of a file, retain bounded windows at real
function declarations throughout the file. Every window is a contiguous slice
of the original source, so a citation's line numbers remain truthful.
"""
from __future__ import annotations

import re
from pathlib import PurePosixPath

_SYMBOL = re.compile(r'^\s*(?:(?:async\s+)?def\s+|(?:export\s+)?(?:async\s+)?function\s+|class\s+|(?:export\s+)?(?:const|let)\s+)([A-Za-z_$][\w$]*)', re.I)
_PRIORITY = ('route', 'rule', 'dispatch', 'request', 'response', 'middleware', 'handler',
             'controller', 'register', 'login', 'auth', 'session', 'token', 'verify',
             'create', 'init', 'main', 'serve', 'execute', 'parse', 'render', 'process',
             'connect', 'database', 'model', 'retrieve', 'index', 'search', 'error')
_CALL_ANCHOR = re.compile(r'\b(?:add_url_rule|url_map\.add|view_functions|dispatch_request|full_dispatch_request|handle_request|handleRequest|registerRoute|middleware)\s*(?:\(|\[)', re.I)
_SOURCE_SUFFIXES = {'.py', '.js', '.ts', '.tsx', '.jsx', '.go', '.rs', '.rb', '.java', '.php', '.cs', '.kt'}


def source_excerpts(source: str, path: str, *, limit: int) -> list[dict]:
    """Return nonoverlapping {start_line,text} windows, bounded by ``limit``.

    No synthetic code, no reordered lines within a window, no omitted-line
    citations. A full, short file stays untouched.
    """
    if limit < 1 or not source:
        return []
    lines = source.splitlines(keepends=True)
    if len(source) <= limit:
        return [{'start_line': 1, 'text': source}]
    if PurePosixPath(path).suffix.lower() not in _SOURCE_SUFFIXES:
        return _windows(lines, [(0, min(8, len(lines)))], limit)
    definitions = []
    for i, line in enumerate(lines):
        match = _SYMBOL.match(line)
        if not match:
            continue
        name = match.group(1)
        words = re.sub(r'([a-z])([A-Z])', r'\1 \2', name).replace('_', ' ').lower()
        priority = sum(3 for term in _PRIORITY if term in words)
        if not line.startswith((' ', '\t')):
            priority += 2
        if not name.startswith('_'):
            priority += 1
        definitions.append((priority, i))
    # Read module imports and context, then a short body around a variety of
    # declarations. A large method never consumes the whole file allowance.
    header_lines = min(14, len(lines))
    unit = min(720, max(180, (limit-400)//max(1, min(12, len(definitions)))))
    regions = [(0, header_lines)]
    # A route declaration often has a very long docstring before the call.
    # Include actual calls throughout the file, not just the signature.
    call_sites = [i for i,line in enumerate(lines) if _CALL_ANCHOR.search(line)]
    if call_sites:
        step = max(1, len(call_sites)//6)
        regions.extend((max(0,i-1), min(len(lines),i+2)) for i in call_sites[::step][:6])
    for _score, at in sorted(definitions, key=lambda x:(-x[0], x[1])):
        if sum(sum(len(line) for line in lines[a:b]) for a,b in regions) > limit - min(unit,300):
            break
        # Include decorators immediately above Python definitions, if present.
        start = at
        while start>0 and at-start<3 and lines[start-1].lstrip().startswith('@'):
            start-=1
        end = start
        remaining = unit
        while end < len(lines) and remaining >= len(lines[end]):
            remaining-=len(lines[end]);end+=1
        if end == start:  # a pathological single very long source line
            end = min(len(lines),start+1)
        regions.append((start, end))
    return _windows(lines, regions, limit)


def _windows(lines: list[str], regions: list[tuple[int, int]], limit: int) -> list[dict]:
    # Priority order determines selection when over budget. Merge overlap only
    # at the end, so the output never treats disjoint excerpts as one passage.
    accepted: set[int] = set()
    total = 0
    for start, end in regions:
        for index in range(start, min(end, len(lines))):
            if index in accepted:
                continue
            if total + len(lines[index]) > limit:
                break
            accepted.add(index)
            total += len(lines[index])
    result=[]
    for number in sorted(accepted):
        if result and result[-1]['end_line']==number:
            result[-1]['text'] += lines[number]
            result[-1]['end_line'] += 1
        else:
            result.append({'start_line':number+1,'end_line':number+1,'text':lines[number]})
    for segment in result:
        del segment['end_line']
    return result
