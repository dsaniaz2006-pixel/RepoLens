import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {setAssignmentTask} from '../src/features/knowledge/assignmentState.mjs';

test('Phase 6: assignment checkbox changes state immutably without waiting for HTTP', () => {
  const before=[{id:'a',data:{snapshot:{tasks:[{id:'read',done:false}]}}},
               {id:'b',data:{snapshot:{tasks:[{id:'read',done:false}]}}}];
  const after=setAssignmentTask(before,'a','read',true);
  assert.equal(after[0].data.snapshot.tasks[0].done,true);
  assert.equal(after[1],before[1]);
  assert.equal(before[0].data.snapshot.tasks[0].done,false);
  assert.equal(setAssignmentTask(after,'a','read',false)[0].data.snapshot.tasks[0].done,false);
});

test('Phase 6: assignment checkbox updates before awaiting the server and rolls back errors',() => {
  const text=readFileSync(new URL('../src/features/knowledge/Assignments.jsx',import.meta.url),'utf8');
  assert.ok(text.includes('setAssignmentTask('),'use immutable optimistic update');
  assert.ok(text.indexOf('setRows(old=>setAssignmentTask(')<text.indexOf('await postJSON(`/api/workspaces/${wid}/assignments/${row.id}/complete`'),
    'checkbox update must not wait for remote response');
  assert.match(text,/catch\s*\(e\)\s*\{\s*setRows\(old=>setAssignmentTask\(/,
    'failed saves must roll back the checkbox');
});
