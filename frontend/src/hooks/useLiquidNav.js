import {useEffect} from 'react';
// One gently moving selection drop, rather than independent heavy shaders.
// Reflective water moves between buttons and remains on one mounted page.
export function useLiquidNav(navRef,page){
 useEffect(()=>{
  const nav=navRef.current;if(!nav)return;
  const move=()=>{
   const current=nav.querySelector('.nav.active');
   const drop=nav.querySelector('.rl-nav-water');
   if(!current||!drop)return;
   drop.style.width=`${current.offsetWidth}px`;
   drop.style.height=`${current.offsetHeight}px`;
   drop.style.transform=`translate(${current.offsetLeft}px,${current.offsetTop}px)`;
   nav.classList.add('has-water');
  };
  const raf=requestAnimationFrame(move);
  const ro=new ResizeObserver(move);ro.observe(nav);
  return()=>{cancelAnimationFrame(raf);ro.disconnect()};
 },[navRef,page]);
}
