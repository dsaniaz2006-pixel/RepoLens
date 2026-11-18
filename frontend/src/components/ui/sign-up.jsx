import React, {useCallback,useEffect,useRef,useState} from 'react';
import {ArrowLeft, ArrowRight, BookOpen, CheckCircle2, Code2, ExternalLink, Github, GitBranch, Layers, LockKeyhole, RefreshCw, ShieldCheck, Sparkles} from 'lucide-react';
import {getProviderAvailability, oauthLoginUrl, postLoginRedirect, AUTH_ERROR_MESSAGES} from './authFlow.mjs';
import './auth.css';

const initialProviders={google:false,github:false};

async function authJSON(url,signal) {
  const response=await fetch(url,{credentials:'same-origin',cache:'no-store',signal});
  if(!response.ok)throw new Error(`HTTP ${response.status}`);
  return response.json();
}

const GoogleMark=()=> <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" width="23" height="23">
  <path d="M20.1 12.2c0-.55-.05-1.1-.15-1.63H12v3.25h4.55a3.86 3.86 0 0 1-1.67 2.53v2.08h2.75c1.63-1.52 2.47-3.74 2.47-6.23Z" fill="currentColor"/>
  <path d="M12 20.5c2.33 0 4.3-.77 5.73-2.07l-2.75-2.08c-.77.5-1.74.8-2.98.8-2.29 0-4.21-1.55-4.9-3.62H4.27v2.18A8.5 8.5 0 0 0 12 20.5Z" fill="currentColor" opacity=".84"/>
  <path d="M7.1 13.53A5.1 5.1 0 0 1 6.84 12c0-.53.09-1.03.26-1.53V8.29H4.27a8.5 8.5 0 0 0 0 7.42l2.83-2.18Z" fill="currentColor" opacity=".66"/>
  <path d="M12 6.84c1.27 0 2.42.44 3.32 1.31l2.48-2.48A8.26 8.26 0 0 0 12 3.5a8.5 8.5 0 0 0-7.73 4.79l2.83 2.18C7.79 8.4 9.71 6.84 12 6.84Z" fill="currentColor" opacity=".9"/>
</svg>;

const RepoLogo=()=> <span className="rl-auth-logo-icon" aria-hidden="true"><svg width="25" height="25" viewBox="0 0 44 44" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round"><path d="M22 3 40 13 22 23 4 13 22 3Z"/><path d="m6 22 16 9 16-9"/><path d="m6 31 16 9 16-9"/></svg></span>;

function StoryScene(){
  return <div className="rl-auth-scene" aria-label="Illustration of how RepoLens connects source code to evidence">
    <div className="rl-scene-back rl-scene-back-one" aria-hidden="true"/>
    <div className="rl-scene-back rl-scene-back-two" aria-hidden="true"/>
    <div className="rl-scene-card">
      <div className="rl-scene-top"><div className="rl-scene-dots" aria-hidden="true"><i/><i/><i/></div><span>CODEBASE / OVERVIEW</span><span className="rl-scene-live"><span/> LIVE PREVIEW</span></div>
      <div className="rl-scene-repo"><span className="rl-scene-repo-icon"><Github size={21}/></span><span><strong>pallets / flask</strong><small>Python · Repository architecture</small></span><Layers size={20} className="rl-scene-mark"/></div>
      <div className="rl-scene-track"><div className="rl-scene-track-title"><GitBranch size={14}/> Verified reading path <span>01 / 04</span></div>
        <div className="rl-scene-step"><span className="rl-scene-index">01</span><span>README.md</span><span className="rl-scene-step-label">ENTRY</span></div>
        <div className="rl-scene-step"><span className="rl-scene-index">02</span><span>pyproject.toml</span><CheckCircle2 size={15}/></div>
        <div className="rl-scene-step rl-scene-selected"><span className="rl-scene-index">03</span><span>src/flask/app.py</span><ArrowRight size={15}/></div>
        <div className="rl-scene-step"><span className="rl-scene-index">04</span><span>src/flask/blueprints.py</span><CheckCircle2 size={15}/></div>
      </div>
      <div className="rl-scene-footer"><ShieldCheck size={15}/><span>Source evidence stays attached to answers</span></div>
    </div>
    <div className="rl-scene-floating" aria-hidden="true"><Sparkles size={16}/> SOURCE AWARE</div>
  </div>;
}

/** RepoLens adaptation of the supplied animated sign-up UI.
 * OAuth-only by design: the backend has no email/password registration endpoint.
 * The illustrative glass interface never fakes an account being created.
 */
export function AuthComponent({logo=<RepoLogo/>,brandName='RepoLens',mode='signup'}){
  const isSignup=mode==='signup';
  const params=new URLSearchParams(window.location.search);
  const next=params.get('next')||'';
  const initialMessage=AUTH_ERROR_MESSAGES[params.get('error')] || (params.get('reason')==='expired'?'Please sign in to open your workspace.':'Checking sign-in options…');
  const [providers,setProviders]=useState(initialProviders);
  const [checking,setChecking]=useState(true);
  const [status,setStatus]=useState(initialMessage);
  const [isRedirecting,setIsRedirecting]=useState(false);
  const activeRequest=useRef(null);

  const loadProviders=useCallback(async()=>{
    activeRequest.current?.abort();
    const controller=new AbortController();
    activeRequest.current=controller;
    const timeout=setTimeout(()=>controller.abort(),15000);
    setChecking(true);
    setProviders(initialProviders);
    setStatus('Checking sign-in options…');
    try {
      const result=await authJSON('/api/auth/providers',controller.signal);
      const nextProviders=getProviderAvailability(result);
      if(controller.signal.aborted)return;
      setProviders(nextProviders);
      const count=Number(nextProviders.google)+Number(nextProviders.github);
      if(!count)setStatus('Google and GitHub sign-in are not configured yet. Add OAuth app credentials to enable accounts.');
      else setStatus(AUTH_ERROR_MESSAGES[params.get('error')]|| (count===2?'Choose a provider to continue securely.':'One sign-in provider is available. The other is awaiting setup.'));
    } catch(error) {
      if(controller.signal.aborted&&activeRequest.current!==controller)return;
      setStatus(error.name==='AbortError'
        ?'The sign-in service took too long. Check that the server is running, then select Check again.'
        :'The sign-in service is unavailable. Check that the server is running, then select Check again.');
    } finally {
      clearTimeout(timeout);
      if(activeRequest.current===controller){activeRequest.current=null;setChecking(false);}
    }
  },[window.location.search]);

  useEffect(()=>{
    loadProviders();
    // Existing session is only trusted when confirmed by the backend.
    const controller=new AbortController();
    authJSON('/api/auth/me',controller.signal).then(data=>{
      if(data?.user?.id&&!controller.signal.aborted)window.location.replace(postLoginRedirect(next));
    }).catch(()=>{});
    return ()=>{controller.abort();activeRequest.current?.abort();};
  },[loadProviders,next]);

  function chooseProvider(provider){
    if(checking||isRedirecting||providers[provider]!==true)return;
    setIsRedirecting(true);
    setStatus('Opening secure sign-in…');
    window.location.assign(oauthLoginUrl(provider,next));
  }
  const otherHref=isSignup?'/login/':'/signup/';
  return <div className="rl-auth" data-auth-page={mode}>
    <div className="rl-auth-atmosphere" aria-hidden="true"><div className="rl-auth-orb rl-auth-orb-one"/><div className="rl-auth-orb rl-auth-orb-two"/><div className="rl-auth-grid"/></div>
    <header className="rl-auth-header"><a href="/" className="rl-auth-brand" aria-label="RepoLens home">{logo}<span>{brandName}</span><span className="rl-auth-brand-dot"/></a><a className="rl-auth-back" href="/"><ArrowLeft size={15}/> Back to website</a></header>
    <main className="rl-auth-layout" id="login">
      <section className="rl-auth-story" aria-label="About RepoLens">
        <p className="rl-auth-eyebrow"><span className="rl-auth-signal"/> YOUR CODE, CLEARLY UNDERSTOOD</p>
        <h1>Understand the <span>whole picture.</span></h1>
        <p className="rl-auth-story-copy">From unfamiliar source files to the story behind your code. Explore architecture, trace flows, and find the evidence.</p>
        <StoryScene/>
        <p className="rl-auth-story-note"><LockKeyhole size={14}/> Private workspaces. Source-backed answers.</p>
      </section>
      <section className="rl-auth-form-area" aria-label={isSignup?'Create your RepoLens account':'Sign in to RepoLens'}>
        <div className="rl-auth-glass-back" aria-hidden="true"/>
        <div className="rl-auth-card">
          <div className="rl-auth-card-icon"><Code2 size={22}/></div>
          <p className="rl-auth-eyebrow">{isSignup?'START YOUR WORKSPACE':'WELCOME BACK'}</p>
          <h2>{isSignup?'Get started with RepoLens.':'Welcome back.'}</h2>
          <p className="rl-auth-card-subtitle">{isSignup?'Create your account and start understanding code with confidence.':'Continue to your private code intelligence workspace.'}</p>
          <div className="rl-auth-divider"><span>CONTINUE SECURELY WITH</span></div>
          <div className="rl-auth-buttons">
            <button type="button" className="rl-auth-provider" data-provider="google" disabled={checking||isRedirecting||!providers.google} onClick={()=>chooseProvider('google')} title={!checking&&!providers.google?'Google OAuth is not configured.':''}>
              <GoogleMark/><span>Continue with Google</span><ArrowRight className="rl-auth-arrow" size={18}/>
            </button>
            <button type="button" className="rl-auth-provider" data-provider="github" disabled={checking||isRedirecting||!providers.github} onClick={()=>chooseProvider('github')} title={!checking&&!providers.github?'GitHub OAuth is not configured.':''}>
              <Github size={23}/><span>Continue with GitHub</span><ArrowRight className="rl-auth-arrow" size={18}/>
            </button>
          </div>
          <p className="rl-auth-provider-note"><ShieldCheck size={16}/> RepoLens never asks for your Google or GitHub password.</p>
          <div className="rl-auth-status-wrap"><p className="rl-auth-status" id="auth-status" role="status" aria-live="polite">{status}</p><button id="provider-retry" type="button" disabled={checking||isRedirecting} onClick={loadProviders}><RefreshCw size={14}/> Check again</button></div>
          <div className="rl-auth-switch">{isSignup?'Already have an account?':'New to RepoLens?'} <a href={otherHref}>{isSignup?'Log in':'Create your account'} <ArrowRight size={14}/></a></div>
        </div>
        <p className="rl-auth-privacy"><BookOpen size={15}/> Explore your codebase, without the noise. <a href="/docs/">Learn more <ExternalLink size={12}/></a></p>
      </section>
    </main>
    <footer className="rl-auth-footer"><span>© RepoLens · AI for code understanding</span><a href="/gallery/">Explore public reports <ArrowRight size={13}/></a></footer>
  </div>;
}
export default AuthComponent;
