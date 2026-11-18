/* RepoLens public-page text reveal. DOM is never replaced, so links and text
   selection remain accessible. Observer stops once each heading is revealed. */
(function(){
 'use strict';
 if(!('IntersectionObserver' in window)||matchMedia('(prefers-reduced-motion: reduce)').matches)return;
 const selector='main h1,main h2,main h3,main h4,main p,main li,main .metric-strip strong,main .metric-strip span,.eyebrow,.rl-hero-title,.auth-title';
 const seen=new WeakSet();
 let order=0;
 const observer=new IntersectionObserver(entries=>{
  entries.forEach(entry=>{
   if(entry.isIntersecting){entry.target.classList.add('rl-reveal-on');observer.unobserve(entry.target)}
  });
 },{threshold:.07,rootMargin:'0px 0px 50px 0px'});
 function discover(){document.querySelectorAll(selector).forEach(node=>{
  if(seen.has(node) || node.closest('[aria-live], [role=alert], pre, code'))return;
  seen.add(node);node.style.setProperty('--rl-reveal-delay',`${(order++%8)*40}ms`);observer.observe(node);
 })}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',discover,{once:true});else discover();
 const mutation=new MutationObserver(discover);
 mutation.observe(document.body,{childList:true,subtree:true});
 window.addEventListener('pagehide',()=>{mutation.disconnect();observer.disconnect()},{once:true});
})();
