import React,{useEffect,useState} from 'react';
import {Activity,RefreshCw} from 'lucide-react';
import {getJSON} from '../../services/apiClient.js';
import {usageRows} from './usageDisplay.mjs';

export default function UsagePanel(){
  const [usage,setUsage]=useState(null);
  const [error,setError]=useState('');
  const [loading,setLoading]=useState(true);
  async function refresh(){
    setLoading(true);setError('');
    try{setUsage(await getJSON('/api/usage'));}
    catch(exc){setError(exc.message);}
    finally{setLoading(false);}
  }
  useEffect(()=>{refresh()},[]);
  const rows=usageRows(usage);
  return <section className="usage-panel" aria-label="Your AI usage" data-testid="section4-usage">
    <div className="usage-heading"><div><h2><Activity size={20}/> Your AI usage</h2>
      <p className="muted">Daily allowances for analysis, conversations and indexing.</p></div>
      <button className="outline" type="button" onClick={refresh} disabled={loading} aria-label="Refresh AI usage"><RefreshCw size={16}/> Refresh</button>
    </div>
    {loading&&!usage?<p role="status">Loading AI usage…</p>:null}
    {error?<p role="alert" className="security-error">{error}</p>:null}
    {usage?<><div className="usage-topline"><span>Current plan: <strong>{usage.plan.toUpperCase()}</strong></span>
      <span>Resets at {new Date(usage.reset_at*1000).toLocaleString()} (midnight UTC)</span></div>
      <div className="usage-bars">{rows.map(row=><div key={row.key} className="usage-bar-row">
        <div className="usage-bar-label"><span>{row.label}</span><strong>{row.used} / {row.limit}</strong></div>
        <div className="usage-bar-track" role="progressbar" aria-label={row.label} aria-valuenow={Math.min(row.used,row.limit)} aria-valuemin={0} aria-valuemax={row.limit||1}>
          <div className="usage-bar-fill" style={{width:`${row.percent}%`}}/></div>
        <small>{row.remaining>0?`${row.remaining} requests remaining`:'Daily allowance used'}</small>
      </div>)}</div>
      <p className="muted usage-note">Requests are counted when they start, including provider failures. Hourly safeguards may apply before daily limits are reached.</p>
    </>:null}
  </section>;
}
