import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { prepareComment, upsertComment, MARKER } = require('../scripts/pr_comment.cjs');

test('Phase 4: produces a bounded, identifiable comment', () => {
  const body = prepareComment('x'.repeat(100000));
  assert.ok(body.startsWith(MARKER + '\n'));
  assert.ok(body.length <= 61000);
  assert.match(body, /truncated/i);
});

test('Phase 4: updates only our own bot comment (never another bot)', async () => {
  const updates=[], creates=[];
  const github={
    paginate: async () => [
      { id:9,user:{type:'Bot',login:'some-other[bot]'},body:MARKER+'\nspoofed'},
      { id:7,user:{type:'Bot',login:'github-actions[bot]'},body:MARKER+'\nold'},
    ],
    rest:{issues:{listComments:()=>{},updateComment:async arg=>updates.push(arg),createComment:async arg=>creates.push(arg)}}
  };
  await upsertComment(github, {repo:{owner:'acme',repo:'service'},issue:{number:42}}, prepareComment('ok'));
  assert.equal(updates.length,1);
  assert.equal(updates[0].comment_id,7);
  assert.deepEqual(creates,[]);
});

test('Phase 4: creates when only spoofed bot comments exist', async () => {
  const creates=[];
  const github={paginate:async () => [{ id:10,user:{type:'Bot',login:'other[bot]'},body:MARKER+'\nignored'}],
      rest:{issues:{listComments:()=>{},updateComment:async()=>{throw Error('should not update')},createComment:async arg=>creates.push(arg)}}};
  await upsertComment(github, {repo:{owner:'acme',repo:'service'},issue:{number:42}}, prepareComment('ok'));
  assert.equal(creates.length,1);
  assert.equal(creates[0].issue_number,42);
});
