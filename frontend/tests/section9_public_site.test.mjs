import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {dirname,join} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=join(dirname(fileURLToPath(import.meta.url)),'..');
const read=p=>readFileSync(join(root,p),'utf8');
const routes=['docs','demo','examples','pricing','blog'];
for(const route of routes){
 test(`Section 9: public /${route}/ page exists with accessible navigation`,()=>{
   const file=`${route}/index.html`;
   assert.ok(existsSync(join(root,file)),file);
   const html=read(file);
   assert.match(html,/<main\b[^>]*id="main"/);
   assert.match(html,/<nav\b[^>]*aria-label=/);
   assert.match(html,/<meta\s+name="viewport"/);
   assert.match(html,new RegExp(`<title>[^<]*RepoLens`));
 });
}
test('all public pages are build entrypoints and linked from landing',()=>{
 const vite=read('vite.config.js'); const home=read('index.html');
 for(const route of routes){
   assert.match(vite,new RegExp(`['"]\\./${route}/index\\.html['"]`));
   assert.match(home,new RegExp(`href="/${route}/"`));
 }
});
test('no payment checkout or fabricated tier prices on public pricing',()=>{
 const html=read('pricing/index.html');
 assert.match(html,/No paid subscriptions/i);
 assert.doesNotMatch(html,/stripe\.com|href="[^"]*checkout|\$\d+\s*\/\s*month/i);
});
test('demo is a labelled pre-generated sample, not an unrestricted AI endpoint',()=>{
 const html=read('demo/index.html');
 assert.match(html,/sample/i);
 assert.match(html,/no live AI requests/i);
 assert.match(html,/\/reports\/pallets-flask-report\.md/);
 assert.doesNotMatch(html,/fetch\([^)]*\/api\/analyze/);
});
test('examples distinguish gallery snapshots from reviewed reports',()=>{
 const html=read('examples/index.html');
 assert.match(html,/<strong>20<\/strong><span>source snapshots/);
 assert.match(html,/<strong>0<\/strong><span>reviewed AI architecture reports/);
 assert.match(html,/href="\/gallery\/"/);
});


test('landing navigation displays Public gallery before Log in, with login last', () => {
  const html=read('index.html');
  const nav=html.match(/<nav class="nav" aria-label="Main navigation">([\s\S]*?)<\/nav>/)?.[1];
  assert.ok(nav, 'landing navigation must exist');
  const gallery=nav.indexOf('href="/gallery/"');
  const login=nav.indexOf('href="/login/"');
  assert.ok(gallery>=0 && login>gallery, 'Public gallery must be before Log in');
  assert.match(nav, /<a class="login-link" href="\/login\/">[\s\S]*?<\/a>\s*$/, 'login must be last');
});
