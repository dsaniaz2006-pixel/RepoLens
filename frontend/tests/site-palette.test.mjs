import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const read = (file) => readFileSync(new URL('../'+file, import.meta.url),'utf8');
const productPages=['docs','blog','pricing','examples','demo'];

test('site-wide palette shares the charcoal blue tokens from the home page',()=>{
  const theme=read('public/site-theme.css');
  assert.match(theme, /#121416/i);
  assert.match(theme, /#222528/i);
  assert.match(theme, /#28547a/i);
  assert.match(theme, /html\[data-repolens-theme="light"\]/);
  for(const page of productPages){
    const html=read(`${page}/index.html`);
    assert.match(html,/\/site-theme\.css/);
    assert.match(html,/\/site\/theme\.js/);
  }
  const gallery=read('gallery/index.html');
  assert.match(gallery,/\/site-theme\.css/);
  assert.match(gallery,/\/site\/theme\.js/);
});

test('dashboard uses persistent, accessible cinematic theme switcher',()=>{
  const app=read('src/main.jsx');
  const switcher=read('src/components/layout/CinematicThemeSwitch.jsx');
  assert.match(app,/CinematicThemeSwitch/);
  assert.match(app,/repolens-theme/);
  assert.match(switcher,/role="switch"/);
  assert.match(switcher,/aria-checked=/);
  assert.match(switcher,/prefers-reduced-motion|reducedMotion|reduce/);
});

test('public theme controller respects stored choice and toggles accessibly',()=>{
  const js=read('site/theme.js');
  assert.match(js,/localStorage/);
  assert.match(js,/repolens-theme/);
  assert.match(js,/data-repolens-theme/);
  assert.match(js,/aria-checked/);
  assert.match(js,/prefers-reduced-motion/);
});

test('dashboard replaces purple and lime decorative colours, keeps functional semantics',()=>{
  const css=read('src/style.css');
  assert.doesNotMatch(css, /#9852f2|#9560fe|#b7d58a|#9b57f4/i);
  assert.match(css, /#121416/i);
  assert.match(css, /#28547a/i);
});
