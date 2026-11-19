import React,{useEffect,useRef,useState} from 'react';
import {WELCOME_SCENE_DURATION_MS,WELCOME_REDUCED_DURATION_MS,welcomeMorphProgress} from '../../lib/motionTiming.mjs';
// Lightweight canvas particle welcome based on the supplied CanvasText motion
// concept. Only one animation per browser session; does not block navigation.
export default function WelcomeScene({user}){
 const [show,setShow]=useState(()=>{
  if(window.matchMedia?.('(max-width: 700px), (prefers-reduced-motion: reduce)')?.matches)return false;
  try{return !sessionStorage.getItem(`repolens-welcome:v21:${user.id}`)}catch{return false}
 });
 const ref=useRef(null);
 useEffect(()=>{
  if(!show)return undefined;
  try{sessionStorage.setItem(`repolens-welcome:v21:${user.id}`,'1')}catch{}
  const reduced=window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  const timer=setTimeout(()=>setShow(false),reduced?WELCOME_REDUCED_DURATION_MS:WELCOME_SCENE_DURATION_MS);
  const canvas=ref.current;
  if(!canvas)return()=>clearTimeout(timer);
  const ctx=canvas.getContext('2d');
  if(!ctx)return()=>clearTimeout(timer);
  const w=canvas.width=620,h=canvas.height=170;
  const message=`Welcome to RepoLens`;
  ctx.fillStyle='#f5f5f3';ctx.textAlign='center';ctx.textBaseline='middle';ctx.font='600 47px system-ui';ctx.fillText(message,w/2,h/2);
  let points=[];
  try{
   const pixels=ctx.getImageData(0,0,w,h).data;
   for(let y=17;y<h-12;y+=4)for(let x=14;x<w-14;x+=4){if(pixels[(y*w+x)*4+3]>120)points.push({x,y,angle:Math.random()*Math.PI*2,r:38+Math.random()*24})}
  }catch{points=[]}
  ctx.clearRect(0,0,w,h);
  let raf=0;
  let startAt=null;
  const paint=(now)=>{
   if(startAt===null)startAt=now;
   const elapsed=Math.max(0,now-startAt);
   ctx.clearRect(0,0,w,h);
   if(!points.length){ctx.fillStyle='#f5f5f3';ctx.font='600 47px system-ui';ctx.textAlign='center';ctx.fillText(message,w/2,h/2);return}
   const t=welcomeMorphProgress(elapsed,reduced);
   ctx.fillStyle='#95c8eb';
   for(const p of points){
    // Quiet orbit before the particles gather into the headline.
    const angle=p.angle+elapsed*.0002;
    const sx=w/2+Math.cos(angle)*p.r,sy=h/2+Math.sin(angle)*p.r;
    ctx.fillRect(sx+(p.x-sx)*t,sy+(p.y-sy)*t,2.4,2.4);
   }
   if(t<1 && !reduced)raf=requestAnimationFrame(paint);
  };
  raf=requestAnimationFrame(paint);
  return()=>{clearTimeout(timer);cancelAnimationFrame(raf)};
 },[show,user.id]);
 if(!show)return null;
 return <div className="rl-welcome-scene" aria-hidden="true"><div className="rl-welcome-inner"><canvas ref={ref} className="rl-welcome-canvas"/><span>Explore your codebase with confidence</span></div></div>;
}
