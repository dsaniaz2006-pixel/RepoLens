import React from 'react';
import {Settings2, RefreshCw, ShieldCheck, Cpu, Github, LockKeyhole, Info} from 'lucide-react';

export default function SettingsOverview({config,busy,onRefresh}){
 const provider=config?.model_provider||'gemini';
 return <div className="settings-overview">
  <div className="settings-banner">
   <div className="settings-banner-heading">
    <div className="settings-banner-mark" aria-hidden="true"><Settings2 size={24}/></div>
    <div className="settings-banner-title">
     <p className="eyebrow">WORKSPACE / SETTINGS</p>
     <h2>Settings &amp; security</h2>
     <p className="muted">Manage AI services, usage, and account protection.</p>
    </div>
   </div>
   <button className="outline settings-refresh" type="button" onClick={onRefresh} disabled={!!busy}>
    <RefreshCw size={16} aria-hidden="true"/> Refresh status
   </button>
  </div>

  <div className="settings-overview-grid config-status">
   <article className="settings-status-card">
    <span className="settings-status-icon" aria-hidden="true"><Cpu size={21}/></span>
    <div className="settings-status-copy">
     <span>AI model provider</span>
     <strong>{provider}</strong>
     <small>{config?.gemini_key_configured?'Provider key configured':'Key setup may be required'}</small>
    </div>
   </article>
   <article className="settings-status-card">
    <span className="settings-status-icon" aria-hidden="true"><Github size={21}/></span>
    <div className="settings-status-copy">
     <span>GitHub API</span>
     <strong>{config?.github_token_configured?'Configured':'Public API'}</strong>
     <small>{config?.github_token_configured?'Token stored on server':'Public API limits may apply'}</small>
    </div>
   </article>
   <article className="settings-status-card">
    <span className="settings-status-icon" aria-hidden="true"><ShieldCheck size={21}/></span>
    <div className="settings-status-copy">
     <span>Credential storage</span>
     <strong>Backend only</strong>
     <small>Secrets are never displayed in the browser</small>
    </div>
   </article>
  </div>

  {config?.message&&<div className="settings-message" role="status"><Info size={17} aria-hidden="true"/>{config.message}</div>}
  <div className="settings-privacy-note">
   <LockKeyhole size={20} aria-hidden="true"/>
   <p>Provider keys remain on the backend, not in the browser. Repository source may be sent to your configured AI provider for analysis and embeddings. Only analyze code you are authorized to share.</p>
  </div>
 </div>;
}
