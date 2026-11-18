import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync, existsSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {join, dirname} from 'node:path';
const root=join(dirname(fileURLToPath(import.meta.url)),'..');

test('all 20 gallery cards link to real snapshots or hash-matched reviewed AI reports',()=>{
 const html=readFileSync(join(root,'gallery','index.html'),'utf8');
 const links=[...html.matchAll(/href="(\/gallery\/[a-z0-9-]+\/index\.html)"/g)].map(x=>x[1]);
 assert.equal(links.length,20);
 const manifestPath=join(root,'public','reports','gallery-manifest.json');
 const manifest=existsSync(manifestPath)?JSON.parse(readFileSync(manifestPath,'utf8')):{};
 for(const link of links){
  const target=join(root,'public',link.slice(1));
  assert.ok(existsSync(target),`${link} must exist in public`);
  const page=readFileSync(target,'utf8');
  const slug=link.split('/')[2];
  if(page.includes('Reviewed AI architecture report')){
   const repo=Object.keys(manifest).find(key=>key.replace('/','-')===slug);
   assert.ok(repo,`${slug} must have a publication receipt`);
   const state=manifest[repo];
   assert.equal(state.type,'reviewed_ai_report');
   assert.ok(state.reviewer && state.reviewed_at && /^[0-9a-f]{40}$/i.test(state.revision));
   const report=join(root,'public','reports',slug+'-report.md');
   assert.ok(existsSync(report));
   assert.equal(createHash('sha256').update(readFileSync(report)).digest('hex'),state.report_sha256);
  }else{
   assert.match(page,/Source snapshot/);
   assert.match(page,/Generation method: deterministic public-source inspection/);
   assert.match(page,/not an AI architecture analysis/);
  }
 }
});
