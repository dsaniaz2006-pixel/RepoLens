import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {join,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=join(dirname(fileURLToPath(import.meta.url)),'..');
const read=path=>readFileSync(join(root,path),'utf8');

test('Phase 10 catalog is linked from the existing dashboard and public home',()=>{
 assert.match(read('src/main.jsx'),/page==='Public Gallery'/);
 assert.match(read('src/main.jsx'),/active\('Public Gallery'\)/);
 assert.match(read('index.html'),/href="\/gallery\/"/);
});

test('Phase 10 has twenty explicit non-misleading report labels and visible navigation',()=>{
 const index=read('gallery/index.html');
 assert.equal([...index.matchAll(/href="\/gallery\/[a-z0-9-]+\/index\.html"/g)].length,20);
 assert.match(index,/20 repositories/);
 const manifestPath=join(root,'public/reports/gallery-manifest.json');
 const published=existsSync(manifestPath)?JSON.parse(readFileSync(manifestPath,'utf8')):{};
 const reviewed=Object.values(published).filter(x=>x?.type==='reviewed_ai_report').length;
 assert.match(index,new RegExp(`${reviewed} reviewed AI architecture reports`));
 assert.match(index,new RegExp(`${20-reviewed} source snapshots`));
 assert.match(index,/href="\/dashboard\/"/);
 assert.ok(existsSync(join(root,'public/gallery/gallery.css')));
 const flask=read('public/gallery/pallets-flask/index.html');
 assert.match(flask,/Source snapshot|Reviewed AI architecture report/);
 assert.match(flask,/href="\/dashboard\/"/);
 assert.match(flask,/href="\/gallery\/"/);
 assert.match(flask,/id="copy-link"/);
});
