/** Shared colour mode for the public, non-dashboard pages.
 * The hero landing and OAuth screens intentionally remain cinematic dark.
 * This module does not use frameworks or affect authentication state.
 */
const storageKey='repolens-theme';
function readMode(){
  try{return window.localStorage.getItem(storageKey)==='light'?'light':'dark';}catch{return 'dark';}
}
function applyMode(mode){
  document.documentElement.setAttribute('data-repolens-theme',mode);
  try{window.localStorage.setItem(storageKey,mode);}catch{}
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content',mode==='dark'?'#121416':'#eef2f4');
  const toggle=document.querySelector('.rl-public-theme-switch');
  if(toggle){toggle.setAttribute('aria-checked',String(mode==='dark'));toggle.title=mode==='dark'?'Switch to light mode':'Switch to dark mode';}
}
applyMode(readMode());
const host=document.querySelector('.product-nav')||document.querySelector('.top nav');
if(host&&!host.querySelector('.rl-public-theme-switch')){
  const toggle=document.createElement('button');
  toggle.type='button';
  toggle.className='rl-public-theme-switch';
  toggle.setAttribute('role','switch');
  toggle.setAttribute('aria-label','Toggle theme');
  toggle.innerHTML=`<svg class="rl-sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42"/></svg><svg class="rl-moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20.5 14A8.5 8.5 0 0 1 10 3.5 8.5 8.5 0 1 0 20.5 14Z"/></svg><span class="rl-public-theme-knob" aria-hidden="true"></span>`;
  toggle.addEventListener('click',()=>{
    const next=document.documentElement.getAttribute('data-repolens-theme')==='dark'?'light':'dark';
    applyMode(next);
    if(!window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches){
      toggle.classList.remove('rl-burst');void toggle.offsetWidth;toggle.classList.add('rl-burst');
      window.setTimeout(()=>toggle.classList.remove('rl-burst'),550);
    }
  });
  host.append(toggle);
  applyMode(readMode());
}
window.addEventListener('storage',(event)=>{if(event.key===storageKey)applyMode(readMode());});
