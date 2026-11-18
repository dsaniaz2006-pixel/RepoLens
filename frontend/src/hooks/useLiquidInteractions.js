import {useEffect} from 'react';
// A single event listener covers all dynamically rendered buttons. Avoids
// initializing one WebGL shader for each action, form button or navigation tab.
export function useLiquidInteractions(rootRef) {
 useEffect(()=>{
  const root=rootRef.current;if(!root)return;
  const pointer=(event)=>{
   if(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)return;
   const button=event.target.closest('button,.gallery-tile');
   if(!button||!root.contains(button)||button.disabled||button.classList.contains('rl-theme-switch'))return;
   const rect=button.getBoundingClientRect();
   const dot=document.createElement('span');
   dot.className='rl-liquid-ripple';dot.setAttribute('aria-hidden','true');
   dot.style.left=`${event.clientX-rect.left}px`;dot.style.top=`${event.clientY-rect.top}px`;
   dot.addEventListener('animationend',()=>dot.remove(),{once:true});
   button.appendChild(dot);
   setTimeout(()=>dot.remove(),700);
  };
  root.addEventListener('pointerdown',pointer);
  return()=>root.removeEventListener('pointerdown',pointer);
 },[rootRef]);
}
