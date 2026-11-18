import React,{useEffect,useState} from 'react';
import {Sun,Moon} from 'lucide-react';

/** Adapted from the supplied cinematic switcher for RepoLens's existing Vite/React stack.
 * No Next.js provider, CSS framework, or animation dependency required.
 * The parent owns the theme; this component only renders the accessible control.
 */
export default function CinematicThemeSwitch({dark,onToggle}){
  const [burst,setBurst]=useState(0);
  useEffect(()=>{
    if(!burst)return;
    const timeout=window.setTimeout(()=>setBurst(0),650);
    return ()=>window.clearTimeout(timeout);
  },[burst]);
  const toggle=()=>{
    const reducedMotion=window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;
    if(!reducedMotion)setBurst(value=>value+1);
    onToggle();
  };
  return <button className={'rl-theme-switch'+(dark?' is-dark':' is-light')} type="button"
    role="switch" aria-checked={dark} aria-label="Toggle theme" title={dark?'Switch to light mode':'Switch to dark mode'} onClick={toggle}>
    <span className="rl-theme-switch-groove" aria-hidden="true"/>
    <Sun className="rl-theme-switch-sun" size={17} aria-hidden="true"/>
    <Moon className="rl-theme-switch-moon" size={17} aria-hidden="true"/>
    <span className="rl-theme-switch-knob" aria-hidden="true">
      {dark?<Moon size={18}/>:<Sun size={18}/>}
      {burst>0&&[0,1,2].map(i=><span key={i} className={'rl-theme-spark rl-theme-spark-'+i}/>)}
    </span>
  </button>;
}
