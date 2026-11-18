import React,{useEffect,useState} from 'react';
import {ArrowLeft,ArrowUpRight,BookOpen,Globe2,Search,ExternalLink} from 'lucide-react';
// Read the gallery's actual published catalog, rather than representing the 20
// source snapshots as reviewed AI reports or inventing report metadata.
export default function GalleryWorkspace({onAnalyze}){
 const [rows,setRows]=useState([]),[summary,setSummary]=useState(''),[picked,setPicked]=useState(null),[error,setError]=useState(''),[filter,setFilter]=useState(''),[copyMessage,setCopyMessage]=useState('');
 useEffect(()=>{let alive=true;fetch('/gallery/',{credentials:'same-origin'}).then(async res=>{if(!res.ok)throw new Error('Gallery unavailable');return res.text()}).then(html=>{
  if(!alive)return;
  const doc=new DOMParser().parseFromString(html,'text/html');
  const entries=[...doc.querySelectorAll('.catalog article')].map(item=>{
   const a=item.querySelector('h2 a');const href=a?.getAttribute('href')||'';
   return {name:a?.textContent?.trim()||'',href,description:item.querySelector('.card-content p')?.textContent?.trim()||'Source snapshot'};
  }).filter(entry=>/^\/gallery\/[a-z0-9-]+\/index\.html$/.test(entry.href));
  setRows(entries);setSummary([...doc.querySelectorAll('.summary > *')].map(el=>el.textContent.trim()).join(' · '));
 }).catch(e=>{if(alive)setError(e.message)});return()=>{alive=false}},[]);
 return <section className="panel gallery-workspace" aria-label="Public Gallery">
  <div className="gallery-head"><div><p className="eyebrow">PUBLIC REPOSITORY LIBRARY</p><h2><Globe2 size={25}/> Public Gallery</h2><p className="muted">Browse cached repository evidence inside your workspace. Source snapshots are not reviewed AI reports.</p></div><button className="primary small" onClick={onAnalyze}><Search size={16}/> Try on your repo</button></div>
  {picked?<div className="gallery-detail"><div className="gallery-detail-bar"><button className="outline" onClick={()=>setPicked(null)}><ArrowLeft size={16}/> All repositories</button><strong>{picked.name}</strong><button className="outline" onClick={async()=>{try{await navigator.clipboard.writeText(new URL(picked.href,window.location.origin).href);setCopyMessage('Report link copied')}catch{setCopyMessage('Copy this URL: '+new URL(picked.href,window.location.origin).href)}}}>Copy report link</button><a className="outline" href={picked.href} target="_blank" rel="noopener noreferrer">Open separately <ExternalLink size={15}/></a></div>{copyMessage&&<p role="status">{copyMessage}</p>}<iframe title={`${picked.name} public report`} className="gallery-report-frame" sandbox="allow-popups allow-popups-to-escape-sandbox" src={picked.href}/></div>:
  <><p className="gallery-summary">{summary||'Loading published catalog…'}</p><label className="gallery-search">Filter repositories<input type="search" value={filter} onChange={e=>setFilter(e.target.value)} placeholder="Search a repository"/></label>
   {error&&<p role="alert">{error}. <a href="/gallery/" target="_blank" rel="noreferrer">Open standalone gallery</a></p>}
   <div className="gallery-tiles">{rows.filter(row=>row.name.toLowerCase().includes(filter.toLowerCase())).map(row=><button className="gallery-tile" key={row.href} onClick={()=>setPicked(row)}><BookOpen size={20}/><span><strong>{row.name}</strong><small>{row.description}</small></span><ArrowUpRight size={18}/></button>)}</div>
   {rows.length===0&&!error&&<p role="status">Loading repositories…</p>}
  </>}
 </section>
}
