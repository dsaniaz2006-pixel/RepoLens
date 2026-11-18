import React,{useEffect,useState} from 'react';
import {getJSON,postJSON} from '../../services/apiClient.js';
import {setAssignmentTask} from './assignmentState.mjs';
export default function Assignments({wid,team}){
 const [rows,setRows]=useState([]),[checklists,setChecklists]=useState([]),[source,setSource]=useState(''),[person,setPerson]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[me,setMe]=useState('');
 const load=async()=>{setRows(await getJSON(`/api/workspaces/${wid}/assignments`));setChecklists(await getJSON('/api/insights/checklist'));setMe((await getJSON('/api/auth/me')).user.id);};
 useEffect(()=>{load().catch(e=>setError(e.message));},[wid]);
 const run=async(fn)=>{setBusy(true);setError('');try{await fn();await load();}catch(e){setError(e.message)}finally{setBusy(false)}};
 const complete=async(row,task,done)=>{
  if(busy||!row.data.active||row.data.assignee!==me)return;
  setRows(old=>setAssignmentTask(old,row.id,task.id,done));
  setBusy(true);setError('');
  try{
   await postJSON(`/api/workspaces/${wid}/assignments/${row.id}/complete`,{task_id:task.id,done});
   await load();
  }catch(e){
   setRows(old=>setAssignmentTask(old,row.id,task.id,task.done));
   setError(e.message);
  }finally{setBusy(false)}
 };
 return <section><h3>Assigned onboarding</h3><p>Assignments preserve the checklist and source revision. Removing a member closes their assignments; rejoining requires a new assignment.</p>{error&&<p role="alert">{error}</p>}{team.role!=='member'&&<><label>Your checklist<select value={source} onChange={e=>setSource(e.target.value)}><option value="">Choose checklist</option>{checklists.map(c=><option key={c.id} value={c.id}>{c.data.repository} · {c.data.revision.slice(0,8)}</option>)}</select></label><label>Assign to member<select value={person} onChange={e=>setPerson(e.target.value)}><option value="">Choose member</option>{team.members.map(m=><option key={m.user} value={m.user}>{m.user}</option>)}</select></label><button disabled={busy||!source||!person} onClick={()=>run(()=>postJSON(`/api/workspaces/${wid}/assignments`,{checklist_id:source,assignee:person}))}>Assign checklist</button></>}{rows.map(row=><article key={row.id}><h4>{row.data.snapshot.repository}</h4><p>Assignee: {row.data.assignee} · {row.data.active?'Active':'Closed'} · {row.data.snapshot.tasks.filter(t=>t.done).length}/{row.data.snapshot.tasks.length} complete</p><small>Revision: {row.data.snapshot.revision} · Checklist version: {row.data.checklist_version.slice(0,12)}</small>{row.data.snapshot.tasks.map(t=><label key={t.id}><input type="checkbox" style={{width:'auto'}} checked={t.done} disabled={busy||!row.data.active||row.data.assignee!==me} onChange={e=>complete(row,t,e.target.checked)}/>{t.phase}: {t.task} — {t.path}:{t.line}</label>)}</article>)}<button disabled={busy} onClick={()=>run(async()=>{})}>Reload assignment progress</button></section>;
}
