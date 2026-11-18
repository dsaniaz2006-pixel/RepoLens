import {useEffect} from 'react';
import {revealDelayMs} from '../lib/motionTiming.mjs';

// Decorative motion only: never split, replace, or hide source text in the DOM.
// Keep buttons, inputs, error alerts, and live status messages usable immediately.
const REVEAL_SELECTOR = [
 'h1','h2','h3','h4','p','li','.eyebrow',
 '.home-stats strong','.home-stats span','.stat-grid > div',
 '.settings-status-card','.gallery-tile','.history-item',
 '.file','.reading','table tbody tr','[data-rl-reveal]'
].join(',');

export function useTextReveal(containerRef,page) {
 useEffect(()=>{
  const root=containerRef.current;
  if(!root || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches || !('IntersectionObserver' in window))return;
  const seen=new Set();
  let order=0;
  const observer=new IntersectionObserver(entries=>{
   for(const entry of entries){
    if(entry.isIntersecting){entry.target.classList.add('rl-text-reveal');observer.unobserve(entry.target)}
   }
  },{threshold:0.07,rootMargin:'0px 0px 44px 0px'});
  const discover=()=>{
   root.querySelectorAll(REVEAL_SELECTOR).forEach(node=>{
    if(seen.has(node) || node.closest('[aria-live], [role="alert"], [role="status"], pre, code'))return;
    seen.add(node);
    node.style.setProperty('--rl-reveal-delay',`${revealDelayMs(order++)}ms`);
    observer.observe(node);
   });
  };
  discover();
  const mutation=new MutationObserver(discover);
  mutation.observe(root,{subtree:true,childList:true});
  return()=>{
   mutation.disconnect();observer.disconnect();
   for(const node of seen){node.classList.remove('rl-text-reveal');node.style.removeProperty('--rl-reveal-delay')}
  };
 },[containerRef,page]);
}
