import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

// Avoid running browser checks against an unrelated RepoLens instance already
// listening on the test port. Exact-match checks keep this independent of Vite.
test('Playwright starts its own dedicated server instead of reusing a stale one',()=>{
 const config=readFileSync(new URL('../playwright.config.js',import.meta.url),'utf8');
 assert.match(config,/reuseExistingServer:\s*false/);
});

test('Phase 6–10 API mocks are installed before React mounts',()=>{
 const spec=readFileSync(new URL('../e2e/phase6_10.spec.js',import.meta.url),'utf8');
 const before=spec.match(/test\.beforeEach\([\s\S]*?\n\}\);/)?.[0] ?? '';
 assert.doesNotMatch(before,/page\.goto\(/);
 assert.match(spec,/async function openWorkspace\(page\)/);
 assert.match(spec,/await openWorkspace\(page\)/);
});


test('Phase 5 loads its workspace fixture before mounting the dashboard',()=>{
 const spec=readFileSync(new URL('../e2e/phase1_5.spec.js',import.meta.url),'utf8');
 const before=spec.match(/test\.beforeEach\([\s\S]*?\n\}\);/)?.[0] ?? '';
 assert.doesNotMatch(before,/page\.goto\(/);
 assert.match(spec,/async function openDashboard\(page\)/);
 const workspace=spec.split("test('Phase 5:")[1];
 assert.ok(workspace.indexOf('await page.route') < workspace.indexOf('await openDashboard(page)'),
   'workspace API mocks must be registered before React first mounts');
});

test('Knowledge Hub navigation is not coupled to the mutation lock',()=>{
 const source=readFileSync(new URL('../src/features/knowledge/KnowledgeHub.jsx',import.meta.url),'utf8');
 assert.match(source,/const choose=\(value\)=>\{/);
 assert.doesNotMatch(source,/const choose=\(value\)=>run\(/);
 assert.match(source,/activeTab\.current=value/);
 assert.match(source,/aria-pressed=\{t===tab\}/);
});

test('Phase 9 verifies that the local panel itself has mounted',()=>{
 const spec=readFileSync(new URL('../e2e/phase6_10.spec.js',import.meta.url),'utf8');
 assert.match(spec,/name:'Private local repository'/);
 assert.match(spec,/getByLabel\('Saved snapshot'\)/);
});
