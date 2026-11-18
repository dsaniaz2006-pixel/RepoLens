import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const ui=readFileSync(new URL('../src/features/knowledge/WorkspaceInvitations.jsx',import.meta.url),'utf8');
const knowledge=readFileSync(new URL('../src/features/knowledge/KnowledgeHub.jsx',import.meta.url),'utf8');
const join=readFileSync(new URL('../public/join.js',import.meta.url),'utf8');
test('teams UI integrates recipient-bound invites and only shows new link once',()=>{
 assert.match(knowledge,/<WorkspaceInvitations workspaceId=\{wid\} role=\{team.role\}/);
 assert.match(ui,/recipient_email: recipient/);
 assert.match(ui,/New invitation link \(shown only once\)/);
 assert.match(ui,/Revoke invitation/);
 assert.match(ui,/role === 'owner' \|\| role === 'admin'/);
});
test('join page explains recipient binding without displaying recipient email',()=>{
 assert.match(join,/recipient_restricted/);
 assert.doesNotMatch(join,/data\.recipient_email/);
});
