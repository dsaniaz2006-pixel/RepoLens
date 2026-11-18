// Invitation URLs are bearer credentials: never log or persist the token.
const token=new URLSearchParams(location.search).get('token')||'';
const status=document.querySelector('#status'),login=document.querySelector('#login'),button=document.querySelector('#join');
let csrf;
async function load(){
 if(!/^[A-Za-z0-9_-]{20,200}$/.test(token))throw Error('Invalid invitation');
 const me=await fetch('/api/auth/me',{cache:'no-store'});
 if(me.status===401){status.textContent='Sign in, then review and confirm this invitation.';login.href='/login/?next='+encodeURIComponent('/join?token='+token);login.hidden=false;return;}
 if(!me.ok)throw Error('Cannot check session. Reload to retry.');
 csrf=(await me.json()).csrf_token;
 const response=await fetch('/api/invitations/'+encodeURIComponent(token),{cache:'no-store'});const data=await response.json();
 if(!response.ok)throw Error(data.detail||'Cannot load invitation');
 status.textContent='Join '+data.name+' as a member?'+(data.recipient_restricted?' This link only works with the invited, verified account email.':'');button.hidden=false;
}
button.onclick=async()=>{button.disabled=true;try{const response=await fetch('/api/workspaces/join',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({token})});const data=await response.json();if(!response.ok)throw Error(data.detail);status.textContent='You joined the workspace. Open the dashboard and select Teams.';button.hidden=true;}catch(e){status.textContent=e.message;button.disabled=false;}};
load().catch(e=>{status.textContent=e.message;});
