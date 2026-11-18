import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
const read=p=>readFileSync(new URL(p,import.meta.url),'utf8');
test('Task 2: Knowledge Hub has explicit button groups and consistent action tokens',()=>{
 const hub=read('../src/features/knowledge/KnowledgeHub.jsx'),css=read('../src/workspace-upgrades.css');
 assert.match(hub,/hub-action-bar/);assert.match(css,/\.hub-action-bar/);assert.match(css,/\.hub-tabs/);
});
test('Task 3: Settings features structured overview cards with live configuration status',()=>{
 assert.match(read('../src/main.jsx'),/SettingsOverview/);assert.match(read('../src/features/settings/SettingsOverview.jsx'),/config-status/);
});
test('Task 4: Gallery renders inside dashboard and preserves sidebar',()=>{
 const main=read('../src/main.jsx'),gallery=read('../src/features/gallery/GalleryWorkspace.jsx');
 assert.match(main,/page==='Public Gallery'/);assert.match(gallery,/gallery\/gallery\.css|\/gallery\//);
 assert.match(gallery,/iframe/);assert.match(main,/gallery-nav/);
});
test('Task 5 revision: native scroll cannot navigate between workspace views',()=>{
 const main=read('../src/main.jsx');
 assert.doesNotMatch(main,/useWorkspaceWheelNavigation/);
 assert.match(main,/onClick=\{\(\)=>active\(n\)\}/);
});
test('Task 6: shared liquid interactions do not replicate a WebGL shader per button',()=>{
 const main=read('../src/main.jsx'),css=read('../src/workspace-upgrades.css');
 assert.match(main,/useLiquidInteractions/);assert.match(css,/\.rl-liquid-ripple/);assert.match(css,/\.app \.nav\.active/);
});
test('Task 7: logo uses charcoal and blue without old lime',()=>{
 const svg=read('../public/favicon.svg');assert.match(svg,/#28547a|#8dbfe5/i);assert.doesNotMatch(svg,/#d6f08d|#193c2d/i);
});
test('Task 8: welcome particle animation is included after authenticated session',()=>{
 assert.match(read('../src/main.jsx'),/WelcomeScene/);assert.match(read('../src/components/layout/WelcomeScene.jsx'),/canvas/);
});
test('Task 9: text reveal is scoped to workspace content and reduced-motion aware',()=>{
 assert.match(read('../src/main.jsx'),/useTextReveal/);const css=read('../src/workspace-upgrades.css');assert.match(css,/rl-text-reveal/);assert.match(css,/prefers-reduced-motion/);
});
