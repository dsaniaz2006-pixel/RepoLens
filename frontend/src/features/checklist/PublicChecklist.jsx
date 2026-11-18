import React,{useEffect,useState} from 'react';
import {getJSON} from '../../services/apiClient.js';

function EvidenceLink({data,task}) {
 const path=task.path.split('/').map(encodeURIComponent).join('/');
 const href=`https://github.com/${data.repository}/blob/${data.revision}/${path}#L${task.line}`;
 return <a href={href} target="_blank" rel="noreferrer">{task.path}:{task.line}{task.end_line!==task.line?`-${task.end_line}`:''}</a>;
}

export default function PublicChecklist({token}) {
 const [data,setData]=useState(null),[error,setError]=useState('');
 useEffect(()=>{
  let active=true;
  getJSON('/api/public/checklists/'+encodeURIComponent(token))
   .then(value=>{if(active)setData(value)})
   .catch(()=>{if(active)setError('This shared checklist is unavailable. The link may be invalid or revoked.')});
  return()=>{active=false};
 },[token]);

 return <div className="app"><main><div className="content">
  <section className="panel report-content">
   <h1>RepoLens · Shared onboarding checklist</h1>
   {error?<p role="alert" className="error">{error}</p>:!data?<p role="status">Loading shared checklist…</p>:<>
    <p><strong>Repository:</strong> {data.repository} · <strong>Revision:</strong> {data.revision}</p>
    <p className="muted">Read-only public view. This link exposes only the onboarding checklist.</p>
    <h2>Checklist</h2>
    {data.tasks.map((task,index)=><article key={index}>
     <h3>{task.phase}: {task.task}</h3>
     <p>{task.done?'Completed':'Not completed'}</p>
     <EvidenceLink data={data} task={task}/>
     <p>{task.why}</p>
     <pre>{task.snippet}</pre>
    </article>)}
    <h2>First contribution guidance</h2>
    <p>{data.first_contribution.task}</p>
    <h3>Files to explore</h3>
    <ul>{data.first_contribution.files.map((path,index)=><li key={index}>{path}</li>)}</ul>
    <h3>Assumptions</h3>
    <ul>{data.first_contribution.assumptions.map((assumption,index)=><li key={index}>{assumption}</li>)}</ul>
   </>}
  </section>
 </div></main></div>;
}
