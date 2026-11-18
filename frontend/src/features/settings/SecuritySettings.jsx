import React, {useEffect, useState} from 'react';
import {ShieldCheck, KeyRound, Laptop, Copy, RefreshCw, Trash2, LogOut, ScrollText} from 'lucide-react';
import {getJSON, postJSON, deleteJSON} from '../../services/apiClient.js';

function dateLabel(timestamp) {
  return typeof timestamp === 'number' ? new Date(timestamp * 1000).toLocaleString() : 'Unavailable';
}

export default function SecuritySettings() {
  const [keys,setKeys]=useState([]);
  const [sessions,setSessions]=useState([]);
  const [events,setEvents]=useState([]);
  const [name,setName]=useState('');
  const [newKey,setNewKey]=useState('');
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const [loading,setLoading]=useState(true);
  const [saving,setSaving]=useState(false);

  async function reload() {
    const [keyList,sessionList]=await Promise.all([getJSON('/api/auth/keys'),getJSON('/api/auth/sessions')]);
    setKeys(keyList.keys || []);
    setSessions(sessionList.sessions || []);
    getJSON('/api/auth/audit').then(result=>setEvents(result.events||[])).catch(()=>{});
  }
  useEffect(()=>{
    let mounted=true;
    Promise.all([getJSON('/api/auth/keys'),getJSON('/api/auth/sessions')])
      .then(([a,b])=>{if(mounted){setKeys(a.keys||[]);setSessions(b.sessions||[]);}})
      .catch(err=>{if(mounted)setError(err.message);})
      .finally(()=>{if(mounted)setLoading(false);});
    getJSON('/api/auth/audit').then(result=>{if(mounted)setEvents(result.events||[]);}).catch(()=>{});
    return ()=>{mounted=false;};
  },[]);
  const create=async(event)=>{
    event.preventDefault();
    if(!name.trim() || saving)return;
    setSaving(true);setError('');setNotice('');setNewKey('');
    try{
      const created=await postJSON('/api/auth/keys',{name:name.trim()});
      setNewKey(created.key);
      setName('');
      await reload();
    }catch(err){setError(err.message);}finally{setSaving(false);}
  };
  const revoke=async(id)=>{
    if(saving || !window.confirm('Revoke this API key? Applications using it will lose access immediately.'))return;
    setSaving(true);setError('');setNotice('');
    try{await deleteJSON('/api/auth/keys/'+encodeURIComponent(id));setNewKey('');await reload();setNotice('API key revoked.');}
    catch(err){setError(err.message);}finally{setSaving(false);}
  };
  const revokeAll=async()=>{
    if(saving || !window.confirm('Sign out every device, including this one?'))return;
    setSaving(true);setError('');
    try{await deleteJSON('/api/auth/sessions/all');window.location.replace('/login/');}
    catch(err){setError(err.message);setSaving(false);}
  };
  const copyKey=async()=>{
    try{await navigator.clipboard.writeText(newKey);setNotice('API key copied. Store it securely: it will not be shown again.');}
    catch{setError('Clipboard access is unavailable. Copy the key manually before leaving this page.');}
  };
  return <section className="security-settings" aria-label="Account security">
    <h2><ShieldCheck size={21}/> Account security</h2>
    <p className="muted">Developer tokens are separate from your Gemini and GitHub credentials. New tokens are shown only once.</p>
    {error&&<p role="alert" className="security-error">{error}</p>}
    {notice&&<p role="status" className="security-notice">{notice}</p>}
    {loading?<p role="status">Loading account security…</p>:<>
      <div className="security-grid">
        <article className="security-card">
          <h3><KeyRound size={19}/> Developer API keys</h3>
          <p className="muted">Create a token to access RepoLens APIs without your browser session. Limit: 10 active keys.</p>
          <form onSubmit={create} className="security-key-form">
            <label htmlFor="section2-key-name">Key name</label>
            <div className="security-create-row"><input id="section2-key-name" value={name} onChange={e=>setName(e.target.value)} maxLength={200} placeholder="My Mac CLI" required/><button className="primary small" disabled={saving||!name.trim()} type="submit">Create API key</button></div>
          </form>
          {newKey&&<div className="security-secret" role="status"><strong>New API key — copy it now</strong><p>This secret will not appear in the list again.</p><code data-testid="section2-secret">{newKey}</code><button className="outline" onClick={copyKey}><Copy size={16}/> Copy API key</button><button className="outline" onClick={()=>setNewKey('')}>I've saved this key</button></div>}
          <h4>Active keys</h4>
          {keys.length===0?<p className="muted">No active developer API keys.</p>:<ul className="security-list">{keys.map(k=><li key={k.id}><div><strong>{k.name}</strong><small>{k.key_prefix}… · Created {dateLabel(k.created_at)}{k.last_used_at?' · Last used '+dateLabel(k.last_used_at):''}</small></div><button className="outline" disabled={saving} onClick={()=>revoke(k.id)} aria-label={'Revoke key '+k.name}><Trash2 size={16}/> Revoke</button></li>)}</ul>}
        </article>
        <article className="security-card">
          <h3><Laptop size={19}/> Signed-in devices</h3>
          <p className="muted">See current sessions and sign out from every device if you suspect unauthorized access.</p>
          {sessions.length===0?<p className="muted">No active sessions.</p>:<ul className="security-list">{sessions.map(s=><li key={s.id}><div><strong>{s.current?'This device':'Another device'}</strong><small>{s.user_agent||'Unknown browser'}{s.ip_address?' · '+s.ip_address:''}</small><small>Expires {dateLabel(s.expires_at)}</small></div>{s.current&&<span className="security-current">Current</span>}</li>)}</ul>}
          <div className="security-actions"><button className="outline" onClick={()=>reload().catch(err=>setError(err.message))} disabled={saving}><RefreshCw size={16}/> Refresh devices</button><button className="outline security-danger" onClick={revokeAll} disabled={saving}><LogOut size={16}/> Sign out all devices</button></div>
        </article>
      </div>
      <article className="security-card security-audit-card">
        <h3><ScrollText size={19}/> Recent security activity</h3>
        <p className="muted">Your most recent security events. Secret values and invitation links are never stored in this log.</p>
        {events.length===0?<p className="muted">No recent security activity.</p>:<ul className="security-list">{events.map(ev=><li key={ev.id}><div><strong>{ev.action.replaceAll('_',' ').replace(':',' — ')}</strong><small>{dateLabel(ev.created_at)}</small></div></li>)}</ul>}
      </article>
    </>}
  </section>;
}
