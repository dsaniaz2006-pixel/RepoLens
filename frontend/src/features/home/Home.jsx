import React from 'react';
import {Search, ArrowRight, FileText, Github, FolderTree, Clock3, BookOpen, Sparkles} from 'lucide-react';
import UsagePanel from '../usage/UsagePanel.jsx';

function Home({user,history,report,busy,onAnalyze,onHistory,onOpen}) {
 const repositories=new Set(history.map(item=>item.metadata?.full_name).filter(Boolean));
 return <div className="home-page">
  <section className="home-welcome"><div><p className="eyebrow">YOUR WORKSPACE</p><h1>{user.first_visit ? 'Welcome' : 'Welcome back'}, {user.name.split(' ')[0]}.</h1><p>{user.first_visit ? 'Your first codebase starts here. Explore a repository to begin.' : 'Pick up a codebase you know, or find your way into a new one.'}</p></div><button className="primary" onClick={onAnalyze}><Search size={18}/> Analyze a repository <ArrowRight size={18}/></button></section>
  <div className="home-stats"><article className="panel"><FileText size={22}/><strong>{history.length}</strong><span>Saved analyses</span></article><article className="panel"><Github size={22}/><strong>{repositories.size}</strong><span>Repositories explored</span></article><article className="panel current-repo"><FolderTree size={22}/><strong>{report?.metadata?.full_name||'Ready to explore'}</strong><span>{report?'Current repository':'Your next codebase starts here'}</span></article></div>
  <UsagePanel/><div className="home-grid"><section className="panel recent-panel"><div className="section-heading"><div><h2><Clock3 size={21}/> Recent analyses</h2><p className="muted">Your saved reports, ready to reopen.</p></div><button className="outline" onClick={onHistory}>View all <ArrowRight size={15}/></button></div>{history.length?history.slice(0,5).map((item)=><button className="history-item" key={item.metadata.full_name} disabled={!!busy} onClick={()=>onOpen(item)}><Github size={20}/><span>{item.metadata.full_name}</span><small>{new Date(item.modified*1000).toLocaleDateString()}</small><ArrowRight size={16}/></button>):<div className="home-empty"><BookOpen size={34}/><h3>Your reading list starts here.</h3><p>Analyze a public GitHub repository to save your first report.</p><button className="outline" onClick={onAnalyze}>Start your first analysis <ArrowRight size={16}/></button></div>}</section>
  <section className="panel quick-start"><h2><Sparkles size={21}/> A useful place to start</h2><ol><li><b>Understand the project</b><p>Open Analyze Repo and paste a public GitHub URL to generate an evidence-backed report.</p></li><li><b>Follow the source</b><p>Explore the technology stack, key files, and recommended reading path.</p></li><li><b>Ask your next question</b><p>Use Ask RepoLens in the report to build a source index and ask code-specific questions.</p></li></ol><button className="primary small" onClick={onAnalyze}>{report?'Continue in Analyze Repo':'Open Analyze Repo'} <ArrowRight size={16}/></button></section></div>
 </div>;
}

export default Home;
