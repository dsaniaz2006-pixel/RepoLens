import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../src/features/knowledge/KnowledgeHub.jsx',import.meta.url),'utf8');
test('checklist checkbox updates local state before awaiting persistence',()=>{
 const at=source.indexOf('type="checkbox" checked={t.done}');
 assert.ok(at>=0,'Checklist checkbox exists');
 const fragment=source.slice(at,at+1100);
 assert.match(fragment,/const done=e\.target\.checked/);
 assert.ok(fragment.indexOf('setResult(')<fragment.indexOf('run(async'), 'optimistic update must precede network request');
 assert.match(fragment,/catch\(error\)\{setResult\(/, 'failed save restores previous state');
});
