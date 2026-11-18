"""Split approved source snippets into line-addressable, stable records."""
from __future__ import annotations
import hashlib
from backend.core.config import CHUNK_SIZE_CHARS, CHUNK_OVERLAP_CHARS


def chunk_files(records, repo_id: str, revision: str, size: int = CHUNK_SIZE_CHARS, overlap: int = CHUNK_OVERLAP_CHARS):
    if size < 1 or not 0 <= overlap < size:
        raise ValueError('Chunk size must be positive and overlap smaller than size')
    chunks = []
    for record in records:
        if record.get('skipped') or not record.get('content'):
            continue
        path = record['path']
        # Each excerpt is a contiguous slice of the original file. NEVER
        # combine disjoint excerpts into one citation line span.
        segments = record.get('segments') or [{'start_line': 1, 'text':record['content']}]
        for segment in segments:
            units = []
            for number, line in enumerate(segment['text'].splitlines(keepends=True), segment['start_line']):
                count = (len(line) + size - 1) // size
                stride = (len(line) + count - 1) // count
                units.extend((number, line[offset:offset + stride])
                             for offset in range(0, len(line), stride))
            lines = [text for _, text in units]
            if not lines:
                continue
            start = 0
            while start < len(lines):
                end, used = start, 0
                while end < len(lines) and used + len(lines[end]) <= size:
                    used += len(lines[end]); end += 1
                piece = ''.join(lines[start:end])
                if piece.strip():
                    first_line, last_line = units[start][0], units[end - 1][0]
                    identity = f'{repo_id}\0{revision}\0{path}\0{first_line}\0{last_line}\0{start}\0{end}\0{piece}'
                    chunks.append({'id': hashlib.sha256(identity.encode()).hexdigest(), 'repo': repo_id,
                                   'revision': revision, 'path': path, 'start_line': first_line,
                                   'end_line': last_line, 'text': piece})
                if end == len(lines):
                    break
                step_back, count = end, 0
                while step_back > start + 1 and count + len(lines[step_back - 1]) <= overlap:
                    step_back -= 1; count += len(lines[step_back])
                start = step_back if step_back < end else end
    return chunks
