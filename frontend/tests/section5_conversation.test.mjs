import test from 'node:test';
import assert from 'node:assert/strict';
import {questionNumber,pinnedCitationUrl} from '../src/features/conversations/conversationDisplay.mjs';

test('question numbering uses durable message position',()=>{
 assert.equal(questionNumber({role:'user',position:1},0),1);
 assert.equal(questionNumber({role:'user',position:15},14),8);
 assert.equal(questionNumber({role:'user'},4),3);
});

test('citation links are pinned to the chat SHA and escaped safely',()=>{
 const url=pinnedCitationUrl('pallets/flask','a'.repeat(40),{path:'src/my module/app.py',start_line:3,end_line:7});
 assert.equal(url,`https://github.com/pallets/flask/blob/${'a'.repeat(40)}/src/my%20module/app.py#L3-L7`);
});

test('untrusted path or revision cannot create misleading GitHub link',()=>{
 const cited={path:'../somewhere',start_line:1,end_line:4};
 assert.equal(pinnedCitationUrl('pallets/flask','a'.repeat(40),cited),null);
 assert.equal(pinnedCitationUrl('pallets/flask','not-a-commit',{...cited,path:'app.py'}),null);
 assert.equal(pinnedCitationUrl('evil.com/r','a'.repeat(40),{...cited,path:'app.py'}),null);
 assert.equal(pinnedCitationUrl('pallets/flask','a'.repeat(40),{...cited,path:'app.py',start_line:-1}),null);
 assert.equal(pinnedCitationUrl('pallets/flask','a'.repeat(40),{...cited,path:'app.py',start_line:5,end_line:4}),null);
});
