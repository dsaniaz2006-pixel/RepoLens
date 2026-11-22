import Home from './features/home/Home.jsx';
import {useWorkspaceNavigation} from './hooks/useWorkspaceNavigation.js';
import SecuritySettings from './features/settings/SecuritySettings.jsx';
import UsagePanel from './features/usage/UsagePanel.jsx';
import KnowledgeHub from './features/knowledge/KnowledgeHub.jsx';
import Conversations from './features/conversations/Conversations.jsx';
import PublicChecklist from './features/checklist/PublicChecklist.jsx';
import React, {useEffect,useLayoutEffect,useState,useRef,useCallback} from 'react';
import {createRoot} from 'react-dom/client';
import {Github, Search, House, Globe2, Clock3, Settings, Sparkles, FileText, FolderTree, BookOpen, ArrowRight, Download, Link as LinkIcon, AlertCircle, Layers, MessageSquare, CheckCircle2, Menu} from 'lucide-react';
import './style.css';
import './theme-switch.css';
import CinematicThemeSwitch from './components/layout/CinematicThemeSwitch.jsx';
import SettingsOverview from './features/settings/SettingsOverview.jsx';
import GalleryWorkspace from './features/gallery/GalleryWorkspace.jsx';
import WelcomeScene from './components/layout/WelcomeScene.jsx';
import {useLiquidInteractions} from './hooks/useLiquidInteractions.js';
import {useTextReveal} from './hooks/useTextReveal.js';
import {useLiquidNav} from './hooks/useLiquidNav.js';
import './workspace-upgrades.css';
const tabs=['Overview','Tech Stack','Key Files','Code Flow','Improvements','First Contribution','Interview','Ask RepoLens'];
import {postJSON, getJSON, setCSRFToken, runIndexJob, streamAnalyze, downloadReport} from './services/apiClient.js';
import {waitForBackend} from './services/backendWake.mjs';
const api=(path,data)=>postJSON('/api/'+path,data);
const text=(x)=>typeof x==='string'?x:JSON.stringify(x||'');

function App({user}){
 const [page,setPage]=useWorkspaceNavigation('Home');
 const [mobileOpen,setMobileOpen]=useState(false);
 const [url,setUrl]=useState('https://github.com/pallets/flask'),[report,setReport]=useState(null),[section,setSection]=useState('Overview'),[busy,setBusy]=useState(''),[error,setError]=useState(''),[history,setHistory]=useState([]),[question,setQuestion]=useState(''),[reply,setReply]=useState(null),[interview,setInterview]=useState(null),[contribution,setContribution]=useState(null),[dark,setDark]=useState(()=>{try{return window.localStorage.getItem('repolens-theme')!=='light'}catch{return true}});
 const [notice,setNotice]=useState(''),[progress,setProgress]=useState(''),[elapsed,setElapsed]=useState(0),[config,setConfig]=useState(null);
 useEffect(()=>{
  const mode=dark?'dark':'light';
  document.documentElement.setAttribute('data-repolens-theme',mode);
  try{window.localStorage.setItem('repolens-theme',mode)}catch{}
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content',dark?'#121416':'#eef2f4');
 },[dark]);
 const controller=useRef(null);
 const appRef=useRef(null),contentRef=useRef(null),navRef=useRef(null);
 useEffect(()=>{getJSON('/api/history').then(setHistory).catch(e=>setError('History could not be loaded: '+e.message))},[]);
 useEffect(()=>{if(!busy)return;const start=Date.now();setElapsed(0);const timer=setInterval(()=>setElapsed(Math.floor((Date.now()-start)/1000)),1000);return()=>clearInterval(timer)},[busy]);

 const inFlight=useRef(false);
 const reportUrl=report?.metadata?.html_url||(report?.metadata?.full_name?`https://github.com/${report.metadata.full_name}`:'');
 const displayReport=(data)=>{setReport(data);setUrl(data.metadata.html_url||`https://github.com/${data.metadata.full_name}`);setPage('Analyze Repo');setSection('Overview');setReply(null);setQuestion('');setInterview(null);setContribution(null)};
 const request=async(type,fn)=>{if(inFlight.current)return;inFlight.current=true;controller.current=new AbortController();setBusy(type);setProgress('');setError('');setNotice('');try{await fn(controller.current.signal)}catch(e){setError(e.message)}finally{inFlight.current=false;controller.current=null;setBusy('');setProgress('')}};
 const analyze=()=>request('Analyzing repository...',async(signal)=>{const r=await streamAnalyze(url,{signal,onProgress:setProgress});displayReport(r);try { const h=await getJSON('/api/history');setHistory(h); } catch(e) {setError('Report generated, but history refresh failed: '+e.message)}});
 const index=()=>request('Indexing repository...',async(signal)=>{const r=await runIndexJob(reportUrl,{signal,onProgress:setProgress});setNotice(`Index ready: ${r.chunks} chunks from ${r.indexed_files} files at revision ${r.revision.slice(0,9)}${r.index_profile ? ` (${r.index_profile} profile)` : ""}${r.reused ? ", reused without re-embedding" : ""}${Number.isFinite(r.build_seconds) ? `; build ${r.build_seconds}s` : ""}${r.timings_seconds ? ` (fetch ${r.timings_seconds.fetch}s, embed ${r.timings_seconds.embedding}s)` : ""}. Ask a question below.`)});
 const ask=()=>question.trim()&&reportUrl&&request('Searching repository...',async()=>{const r=await api('ask',{url:reportUrl,question});setReply(r)});
 const buildInterview=()=>request('Generating source-backed interview questions...',async()=>{const r=await api('interview',{url:reportUrl});setInterview(r)});
 const buildContribution=()=>request('Investigating a first contribution...',async()=>{const r=await api('contribution',{url:reportUrl});setContribution(r)});
 const openOld=async(x)=>request('Loading saved report...',async()=>{const name=x.metadata.full_name.split('/');const data=await getJSON('/api/history/'+name.join('/'));displayReport(data)});
 const a=report?.analysis||{},m=report?.metadata||{};const files=(report?.tree||[]).filter(x=>x.type==='blob').slice(0,50);
 const refreshConfig=()=>request('Checking server configuration...',async()=>{setConfig(await getJSON('/api/config-status'))});
 const active=useCallback((name)=>{
  setMobileOpen(false);
  if(name===page)return;
  setPage(name);
  if(name==='Settings')getJSON('/api/config-status').then(setConfig).catch(e=>setError(e.message));
 },[page]);
 // Reset scroll after the new view is mounted but before it is painted. This
 // avoids exposing the middle of a different page when navigating backwards.
 useLayoutEffect(()=>{window.scrollTo(0,0);},[page]);
 useLiquidInteractions(appRef);
 useLiquidNav(navRef,page);
 useTextReveal(contentRef,page);
 const copyLink=async()=>{try{await navigator.clipboard.writeText(reportUrl||window.location.href);setNotice(reportUrl?'Repository link copied.':'Workspace link copied.')}catch{setError('Clipboard access failed. Copy this link manually: '+(reportUrl||window.location.href))}};
 const download=(format)=>request('Preparing download...',async()=>{await downloadReport('/api/report/'+m.full_name+(format==='pdf'?'/pdf':''),m.full_name.replace('/','-')+'-report.'+format);setNotice('Report download started.')});
 const signOut=()=>request('Signing out...',async()=>{
  await api('auth/logout',{});
  window.location.replace('/login/');
 });
 useEffect(()=>{
  if(!mobileOpen)return;
  const oldOverflow=document.body.style.overflow;
  const onEscape=(event)=>{
   if(event.key==='Escape')setMobileOpen(false);
  };
  document.body.style.overflow='hidden';
  window.addEventListener('keydown',onEscape);
  window.requestAnimationFrame(()=>{
   document.querySelector('.app.mobile-open .side nav button')?.focus({preventScroll:true});
  });
  return ()=>{
   document.body.style.overflow=oldOverflow;
   window.removeEventListener('keydown',onEscape);
  };
 },[mobileOpen]);
 useEffect(()=>{
  const query=window.matchMedia('(max-width:700px)');
  const update=()=>{if(!query.matches)setMobileOpen(false)};
  query.addEventListener?.('change',update);
  return ()=>query.removeEventListener?.('change',update);
 },[]);
 return <div ref={appRef} className={(dark?'app':'app light')+(mobileOpen?' mobile-open':'')}>
 <WelcomeScene user={user}/>
 <div className="rl-mobile-topbar">
  <span className="rl-mobile-identity">
   <img src="/favicon-v2.svg?v=20" alt="" width="34" height="34"/>
   RepoLens
  </span>
  <button type="button" className="rl-mobile-menu"
   aria-label="Open navigation"
   aria-expanded={mobileOpen}
   aria-controls="repolens-mobile-navigation"
   onClick={()=>setMobileOpen(true)}>
   <Menu size={25}/>
  </button>
 </div>
 {mobileOpen&&<button type="button" className="rl-mobile-backdrop"
  aria-label="Close navigation overlay"
  onClick={()=>setMobileOpen(false)}/>}
 <aside className="side" id="repolens-mobile-navigation"
  aria-label="Workspace navigation drawer"
  role={mobileOpen?'dialog':undefined}
  aria-modal={mobileOpen?'true':undefined}>
 <div className="brand"><img className="brand-logo" src="/favicon-v2.svg?v=20" alt="" width="40" height="40"/><div><h2>RepoLens</h2><small>Understand any GitHub repo with AI</small></div></div><nav ref={navRef} aria-label="Workspace navigation"><span className="rl-nav-water" aria-hidden="true"/>{[['Home',House],['Analyze Repo',Search],['Knowledge Hub',BookOpen],['Conversations',MessageSquare],['Past Analyses',Clock3],['Settings',Settings]].map(([n,Icon])=><button key={n} className={page===n?'nav active':'nav'} aria-current={page===n?'page':undefined} onClick={()=>active(n)}><Icon size={21}/>{n}</button>)}<button className={page==='Public Gallery'?'nav gallery-nav active':'nav gallery-nav'} type="button" aria-current={page==='Public Gallery'?'page':undefined} onClick={()=>active('Public Gallery')}><Globe2 size={21}/>Public Gallery</button></nav>
 <div className="rl-mobile-tools">
  <div className="rl-mobile-account">
   <span className="avatar">{user.name.slice(0,1).toUpperCase()}</span>
   <span>{user.name}</span>
  </div>
  <div className="rl-mobile-appearance">
   <span>Appearance</span>
   <CinematicThemeSwitch dark={dark} onToggle={()=>setDark(v=>!v)}/>
  </div>
  <button className="outline rl-mobile-signout" type="button"
   disabled={!!busy} onClick={signOut}>Sign out</button>
 </div>
 <div className="powered">Powered by<br/><span><Github size={22}/> GitHub API</span><span><Sparkles size={22}/> Google Gemini</span></div></aside><main><header><div className="top-right"><CinematicThemeSwitch dark={dark} onToggle={()=>setDark(v=>!v)}/><span className="avatar" title={user.name}>{user.name.slice(0,1).toUpperCase()}</span><button className="outline" disabled={!!busy} onClick={signOut}>Sign out</button></div></header><div key={page} ref={contentRef} className="content rl-workspace-content" role="region" aria-label={`${page} content`}>{page==='Analyze Repo'&&<><section className="hero"><div><h1>Analyze a repository.<br/><em>Explore the evidence.</em></h1><p>Get an AI-powered analysis of the project structure, purpose,<br/> technologies, code flow and more.</p></div><div className="hero-art"><Github size={80}/><ArrowRight size={33}/><FileText size={84}/></div></section>
 <div className="searchbar"><LinkIcon/><input aria-label="GitHub URL" value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://github.com/owner/repo"/><button onClick={analyze} disabled={!!busy}><Sparkles size={17}/>{busy==='Analyzing repository...'?'Analyzing…':'Analyze Repository'}</button></div></>}
 {busy&&<div className="operation-status" role="status" aria-live="polite"><div><strong>{busy}</strong><p>{progress||'Waiting for the server. Provider requests can take a few minutes.'}</p><small>Elapsed: {elapsed}s. You can browse other workspace pages.</small></div>{busy==='Analyzing repository...'&&<button className="outline" onClick={()=>controller.current?.abort()}>Stop waiting</button>}{busy==='Indexing repository...'&&<button className="outline" onClick={()=>{controller.current?.abort();setProgress('Requesting cancellation…')}}>Cancel indexing</button>}</div>}
 {notice&&<div className="success-message" role="status"><CheckCircle2 size={18}/>{notice}</div>}
 {error&&<div role="alert" className="error"><AlertCircle size={18}/>{error}</div>}
 {page==='Knowledge Hub'?<KnowledgeHub initialRepo={reportUrl||url}/>:page==='Conversations'?<Conversations initialRepo={reportUrl||url}/>:page==='Public Gallery'?<GalleryWorkspace onAnalyze={()=>active('Analyze Repo')}/>:page==='Home'?<Home user={user} history={history} report={report} busy={busy} onAnalyze={()=>active('Analyze Repo')} onHistory={()=>active('Past Analyses')} onOpen={openOld}/>:page==='Past Analyses'?<section className="panel"><h2><Clock3/> Past Analyses</h2>{history.length===0?<p className="muted">No saved analyses. Analyze a repository to get started.</p>:history.map((h,i)=><button className="history-item" key={i} disabled={!!busy} onClick={()=>openOld(h)}><Github/> {h.metadata.full_name} <small>{new Date(h.modified*1000).toLocaleString()}</small></button>)}</section>:page==='Settings'?<section className="panel settings-page"><SettingsOverview config={config} busy={busy} onRefresh={refreshConfig}/><UsagePanel/><SecuritySettings/></section>:<div className="columns"><div className="panel report"><div className="report-head"><div><h2><FileText/> Analysis Report</h2><p className="muted">{m.full_name?'Repository: '+m.full_name:'Run an analysis to generate a real report'}</p></div><div className="actions">{m.full_name&&<button className="outline" disabled={!!busy} onClick={()=>download('md')}><Download size={17}/> Markdown</button>}{m.full_name&&<button className="outline" disabled={!!busy} onClick={()=>download('pdf')}><Download size={17}/> PDF</button>}<button className="outline" onClick={copyLink}><LinkIcon size={16}/> Copy Repository Link</button></div></div><div className="tabs">{tabs.map(t=><button key={t} className={section===t?'tab selected':'tab'} onClick={()=>setSection(t)}>{t}</button>)}</div>
 {!report?<div className="empty"><Sparkles size={45}/><h2>Your codebase, explained.</h2><p>Enter a public GitHub repository URL and click Analyze Repository. Results here are generated from real source evidence, not sample data.</p></div>:<div className="report-content">
 {section==='Overview'&&<><h2>🎯 Project Overview</h2><p>{a.project_summary}</p><div className="stat-grid"><div><small>Repository</small><a href={m.html_url} target="_blank" rel="noreferrer">{m.full_name}</a></div><div><small>Language</small>{m.language||'Not specified'}</div><div><small>Branch</small>{m.default_branch}</div><div><small>Files shown</small>{files.length}</div></div><h2><Layers/> Repository Map</h2>{(a.repository_map||[]).map((x,i)=><article key={i}><b>{x.path}</b><p>{x.purpose}</p></article>)}<h2>Limitations</h2>{(a.limitations||[]).map((x,i)=><p key={i}>{text(x)}</p>)}</>}
 {section==='Tech Stack'&&<><h2>Technology Stack</h2>{(a.tech_stack||[]).map((x,i)=><article key={i}><h3>{x.name}</h3><p>{x.explanation}</p><small>{(x.evidence_paths||[]).join(', ')}</small></article>)}</>}
 {section==='Key Files'&&<><h2>Recommended Reading Path</h2>{(a.reading_path||[]).map((x,i)=><article key={i}><h3>{i+1}. {x.path}</h3><p>{x.reason}</p></article>)}<h2>Entry Points</h2>{(a.entry_points||[]).map((x,i)=><article key={i}><b>{x.path}</b><p>{x.reason}</p></article>)}</>}
 {section==='Code Flow'&&<><h2>Code Flow</h2><p>{a.code_flow?.summary||'Not enough evidence'}</p><small>{a.code_flow?.supported?'Supported by selected repository evidence':'Uncertain / not confirmed'}</small>{(a.code_flow?.steps||[]).map((x,i)=><article key={i}><h3>{i+1}. {x.path}</h3><p>{x.role}</p><small>{x.evidence}</small></article>)}</>}
 {section==='Improvements'&&<><h2>Evidence-based Improvement</h2><p>{a.improvement_idea?.idea||'Not enough evidence'}</p><h3>Evidence</h3><p>{(a.improvement_idea?.evidence_paths||[]).join(', ')}</p><h3>Assumptions</h3><p>{(a.improvement_idea?.assumptions||[]).map(text).join(' • ')}</p></>}
 {section==='First Contribution'&&<><h2>First Contribution Candidate</h2><p className="muted">A source-backed suggestion for human review, never a verified open issue or confirmed bug.</p><button className="primary small" disabled={!!busy} onClick={buildContribution}>Generate Contribution Candidate</button>{contribution&&<article><h3>{contribution.task}</h3><p>{contribution.why_beginner_friendly}</p><h3>Evidence paths</h3><p>{(contribution.evidence_paths||[]).join(', ')}</p><h3>Investigation plan</h3><ol>{(contribution.investigation_plan||[]).map((v,i)=><li key={i}>{v}</li>)}</ol><h3>Risks</h3><ul>{(contribution.risks||[]).map((v,i)=><li key={i}>{v}</li>)}</ul><p className="muted">Unverified: {contribution.unverified}</p></article>}</>}
 {section==='Interview'&&<><h2>Repository Interview Mode</h2><p className="muted">Generate five repository-specific questions with file evidence and verification notes.</p><button className="primary small" disabled={!!busy} onClick={buildInterview}>Generate 5 Interview Questions</button>{(interview?.questions||[]).map((item,i)=><article key={i}><h3>{i+1}. {item.question}</h3><p>{item.answer}</p><small>Sources: {(item.evidence_paths||[]).join(', ')}</small><p className="muted">Verification: {item.verification_note}</p></article>)}</>}
 {section==='Ask RepoLens'&&<><h2>Ask the Repository</h2><p>Open saved conversations to build an index and ask follow-up questions with source citations.</p><button className="primary small" onClick={()=>active('Conversations')}>Open conversations</button></>}

 </div>}</div><aside className="right"><div className="panel"><h3><FolderTree/> Repository Structure</h3>{files.length===0?<p className="muted">Repository structure appears after analysis.</p>:files.map((f,i)=><div className="file" key={i}><FileText size={15}/><span title={f.path}>{f.path}</span></div>)}</div><div className="panel"><h3><BookOpen/> Recommended Files to Read First</h3>{!a.reading_path?.length?<p className="muted">Evidence-based reading paths appear after analysis.</p>:a.reading_path.map((x,i)=><div className="reading" key={i}><span>{i+1}</span><div><b>{x.path}</b><small>{x.reason}</small></div></div>)}</div></aside></div>}
 </div></main></div>
}

// Never mount the workspace until the server confirms a valid session.
const root = createRoot(document.getElementById('root'));
const sharedChecklistToken = new URLSearchParams(window.location.search).get('checklist');
if(sharedChecklistToken){
 root.render(<PublicChecklist token={sharedChecklistToken}/>);
}else{
 root.render(<div role="status" style={{padding:40,color:'#182b24'}}>Checking your session…</div>);
 async function verifySession() {
  const data=await getJSON('/api/auth/me');
  if (!data.user?.id || !data.csrf_token) throw new Error('Invalid session response. Retry after checking the API server.');
  setCSRFToken(data.csrf_token);
  return data.user;
 }
 function startWorkspace(){
  const showConnecting = ({attempt}) => root.render(
   <div role="status" aria-live="polite" style={{minHeight:'100vh',background:'#121416',color:'#f5f5f3',display:'grid',placeItems:'center',padding:28,textAlign:'center'}}>
    <div style={{maxWidth:440}}><h2>Connecting to RepoLens server…</h2>
     <p style={{color:'#aebbd1',lineHeight:1.6}}>The backend may be waking up after inactivity. This can take about a minute on Render Free.</p>
     <p style={{color:'#88bee4'}}>Connection attempt {attempt}</p>
    </div>
   </div>
  );
  showConnecting({attempt:1});
  waitForBackend({onProgress:showConnecting})
   .then(()=>verifySession())
   .then(user=>root.render(<App user={user}/>))
   .catch(error=>root.render(<div role="alert" style={{minHeight:'100vh',padding:30,background:'#121416',color:'#f5f5f3'}}>
    <h2>Unable to check your session</h2><p>{error.message}</p>
    <button type="button" onClick={startWorkspace}>Retry connection</button>
    <p><a href="/login/">Go to login</a></p>
   </div>));
 }
 startWorkspace();
 // Only HTTP 401 triggers a login redirect in readJSON; a network interruption
 // during tab focus must not throw away the user's current report.
 window.addEventListener('focus', ()=>verifySession().catch(()=>{}));
}
window.addEventListener('pageshow', event=>{if(event.persisted)window.location.reload()});
