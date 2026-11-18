import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync,readFileSync,readdirSync,statSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {resolve,dirname,extname} from 'node:path';

const base=fileURLToPath(new URL('../src/',import.meta.url));
const file=(name)=>resolve(base,name);

test('feature components, hooks, state and API services have dedicated modules',()=>{
 for(const name of [
  'features/home/Home.jsx','features/knowledge/KnowledgeHub.jsx',
  'features/conversations/Conversations.jsx','features/settings/SecuritySettings.jsx',
  'features/gallery/GalleryWorkspace.jsx','features/usage/UsagePanel.jsx',
  'components/layout/WelcomeScene.jsx','hooks/useLiquidNav.js',
  'hooks/useTextReveal.js','state/workspaceNavigation.mjs',
  'services/apiClient.js','lib/motionTiming.mjs',
 ]) assert.ok(existsSync(file(name)),`Missing ${name}`);
 for(const name of ['main.jsx','auth.jsx','apiClient.js','style.css']) assert.ok(existsSync(file(name)));
});

test('all local static imports inside src point to existing files',()=>{
 function visit(dir){
  for(const item of readdirSync(dir)){
   const absolute=resolve(dir,item);
   if(statSync(absolute).isDirectory()){visit(absolute);continue;}
   if(!['.js','.jsx','.mjs'].includes(extname(item)))continue;
   const source=readFileSync(absolute,'utf8');
   const re=/(?:\bfrom\s*|\bimport\s*)['"](\.[^'"]+)['"]/g;
   for(const match of source.matchAll(re)){
    const candidate=resolve(dirname(absolute),match[1]);
    assert.ok(existsSync(candidate),`${absolute}: missing ${match[1]}`);
   }
  }
 }
 visit(base);
});
