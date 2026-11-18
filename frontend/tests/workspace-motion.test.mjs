import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {
 REVEAL_STAGGER_MS,REVEAL_DURATION_MS,
 WELCOME_SCENE_DURATION_MS,WELCOME_REDUCED_DURATION_MS,
 revealDelayMs,welcomeMorphProgress
} from '../src/lib/motionTiming.mjs';
const src=(path)=>readFileSync(new URL(path,import.meta.url),'utf8');

test('workspace uses deliberate navigation only; wheel cannot switch pages',()=>{
 const main=src('../src/main.jsx');
 assert.doesNotMatch(main,/useWorkspaceWheelNavigation|WORKSPACE_SCROLL_ORDER|data-workspace-direction/);
 assert.doesNotMatch(main,/["']wheel["']|onWheel=/);
 assert.match(main,/onClick=\{\(\)=>active\(n\)\}/);
 assert.match(main,/key=\{page\} ref=\{contentRef\}/);
 assert.equal(existsSync(new URL('../src/useWorkspaceWheelNavigation.js',import.meta.url)),false);
 assert.equal(existsSync(new URL('../src/workspaceWheelTiming.js',import.meta.url)),false);
});

test('welcome takes 4.2s with a gentle ease and reduced-motion fast exit',()=>{
 assert.equal(WELCOME_SCENE_DURATION_MS,4200);
 assert.equal(WELCOME_REDUCED_DURATION_MS,500);
 assert.equal(welcomeMorphProgress(0),0);
 assert.equal(welcomeMorphProgress(360),0);
 assert.ok(welcomeMorphProgress(1300)>0 && welcomeMorphProgress(1300)<1);
 assert.equal(welcomeMorphProgress(3200),1);
 assert.equal(welcomeMorphProgress(0,true),1);
 const scene=src('../src/components/layout/WelcomeScene.jsx');
 const css=src('../src/workspace-upgrades.css');
 assert.match(scene,/requestAnimationFrame\(paint\)/);
 assert.match(scene,/WELCOME_SCENE_DURATION_MS/);
 assert.match(css,/rl-welcome-depart 4\.2s/);
 assert.match(css,/rl-welcome-depart \.5s/);
});

test('40ms stagger with 950ms full reveal on workspace and public pages',()=>{
 assert.equal(REVEAL_STAGGER_MS,40);
 assert.equal(REVEAL_DURATION_MS,950);
 assert.deepEqual(Array.from({length:10},(_,i)=>revealDelayMs(i)),[0,40,80,120,160,200,240,280,0,40]);
 const hook=src('../src/hooks/useTextReveal.js');
 const css=src('../src/workspace-upgrades.css');
 const publicJs=src('../public/site/reveal.js');
 const publicCss=src('../public/reveal.css');
 assert.match(hook,/settings-status-card/);
 assert.match(hook,/table tbody tr/);
 assert.match(hook,/IntersectionObserver/);
 assert.match(css,/rl-reveal-words \.95s/);
 assert.match(publicJs,/\*40/);
 assert.match(publicCss,/rl-public-text-reveal \.95s/);
 assert.match(css,/prefers-reduced-motion:reduce/);
 assert.match(publicCss,/prefers-reduced-motion:reduce/);
});

test('manual page click preserves unique view and keyboard accessibility',()=>{
 const main=src('../src/main.jsx'),css=src('../src/workspace-upgrades.css');
 assert.match(main,/aria-current=\{page===n\?'page':undefined\}/);
 assert.match(css,/rl-workspace-click-enter 300ms/);
 assert.match(css,/Page views change only from intentional clicks/);
 assert.doesNotMatch(css,/rl-workspace-smooth-enter|rl-workspace-arrive/);
});
