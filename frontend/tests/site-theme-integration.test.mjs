import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

/** Exercise the actual public theme script without a browser or network. */
test('public page toggle persists a choice and updates accessible switch state',()=>{
  const persisted=new Map();
  const rootAttrs=new Map();
  const elementAttrs=new Map();
  let click=()=>{};
  const btn={
    className:'',type:'',title:'',innerHTML:'',offsetWidth:66,
    setAttribute(key,value){elementAttrs.set(key,value)},
    addEventListener(type,fn){if(type==='click')click=fn},
    classList:{add(){},remove(){}},
  };
  const host={querySelector(){return null},append(node){assert.equal(node,btn)}};
  const meta={setAttribute(k,v){rootAttrs.set('meta:'+k,v)}};
  const context={
    document:{
      documentElement:{setAttribute:(k,v)=>rootAttrs.set(k,v),getAttribute:(k)=>rootAttrs.get(k)},
      querySelector:(selector)=>selector==='.product-nav'?host:selector==='.rl-public-theme-switch'?btn:selector==='meta[name="theme-color"]'?meta:null,
      createElement:()=>btn,
    },
    window:{
      localStorage:{getItem:k=>persisted.get(k)||null,setItem:(k,v)=>persisted.set(k,v)},
      matchMedia:()=>({matches:true}),
      setTimeout:()=>0,
      addEventListener:()=>{},
    },
  };
  vm.runInNewContext(readFileSync(new URL('../site/theme.js',import.meta.url),'utf8'),context);
  assert.equal(rootAttrs.get('data-repolens-theme'),'dark');
  assert.equal(elementAttrs.get('aria-checked'),'true');
  assert.equal(elementAttrs.get('aria-label'),'Toggle theme');
  click();
  assert.equal(rootAttrs.get('data-repolens-theme'),'light');
  assert.equal(rootAttrs.get('meta:content'),'#eef2f4');
  assert.equal(elementAttrs.get('aria-checked'),'false');
  assert.equal(persisted.get('repolens-theme'),'light');
  click();
  assert.equal(rootAttrs.get('data-repolens-theme'),'dark');
  assert.equal(persisted.get('repolens-theme'),'dark');
});
