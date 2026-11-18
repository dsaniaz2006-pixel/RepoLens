import React from 'react';
import {Settings2, RefreshCw, ShieldCheck, Cpu, Github, LockKeyhole, Info} from 'lucide-react';
export default function SettingsOverview({config,busy,onRefresh}){
 const provider=config?.model_provider||'gemini';
 return <div className="settings-overview">
  <div className="settings-banner">
   <div className="settings-banner-mark"><Settings2 size={28}/></div>
   <div className="settings-banner-title"><p className="eyebrow">YOUR WORKSPACE / CONFIGURATION</p><h2>Settings &amp; security</h2><p className="muted">Manage AI provider visibility, account protection, and usage in one place.</p></div>
   <button className="outline" type="button" onClick={onRefresh} disabled={!!busy}><RefreshCw size={16}/> Refresh status</button>
  </div>
  <div className="settings-overview-grid config-status">
   <article className="settings-status-card"><Cpu size={21}/><span>AI model provider</span><strong>{provider}</strong><small>{config?.gemini_key_configured?'Provider key configured':'Key setup may be required'}</small></article>
   <article className="settings-status-card"><Github size={21}/><span>GitHub API</span><strong>{config?.github_token_configured?'Configured':'Public API'}</strong><small>{config?.github_token_configured?'Token stored on server':'Public API limits may apply'}</small></article>
   <article className="settings-status-card"><ShieldCheck size={21}/><span>Credential storage</span><strong>Backend only</strong><small>Provider secrets are never displayed in browser code</small></article>
  </div>
  {config?.message&&<div className="settings-message" role="status"><Info size={17}/>{config.message}</div>}
  <div className="settings-privacy-note"><LockKeyhole size={20}/><p>API keys stay in the local server <code>.env</code>. Repository source is sent to your configured AI provider for analysis and embeddings. Only analyze code you are authorized to share.</p></div>
 </div>
}
