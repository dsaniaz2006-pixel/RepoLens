import React, {useCallback, useEffect, useState} from 'react';
import {getJSON, postJSON, deleteJSON} from '../../services/apiClient.js';

/** One-time invite links; the secret is only kept in memory until the user leaves. */
export default function WorkspaceInvitations({workspaceId, role}) {
  const [email, setEmail] = useState('');
  const [link, setLink] = useState('');
  const [pending, setPending] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const canManage = role === 'owner' || role === 'admin';
  const refresh = useCallback(async () => {
    if (!workspaceId || !canManage) return;
    const result = await getJSON(`/api/workspaces/${encodeURIComponent(workspaceId)}/invitations`);
    setPending(result);
  }, [workspaceId, canManage]);
  useEffect(() => {
    setLink(''); setEmail(''); setNotice(''); setError(''); setPending([]);
    if (canManage) refresh().catch(err => setError(err.message));
  }, [workspaceId, canManage, refresh]);
  if (!canManage || !workspaceId) return null;
  async function perform(operation) {
    if (busy) return;
    setBusy(true); setError(''); setNotice('');
    try { await operation(); await refresh(); }
    catch (err) { setError(err.message || 'Invitation operation failed'); }
    finally { setBusy(false); }
  }
  async function create() {
    await perform(async () => {
      const recipient = email.trim();
      const payload = recipient ? {recipient_email: recipient} : {};
      const result = await postJSON(`/api/workspaces/${encodeURIComponent(workspaceId)}/invite`, payload);
      setLink(result.url);
      setNotice(recipient ? 'Invitation restricted to the verified email you entered. Share the link privately.'
        : 'Unrestricted single-use link. Anyone signed in with the link can join; share it privately.');
    });
  }
  async function copyLink() {
    try { await navigator.clipboard.writeText(link); setNotice('Invitation link copied.'); }
    catch { setError('Clipboard unavailable. Select and copy the link manually.'); }
  }
  return <section className="workspace-invitations" aria-label="Workspace invitations">
    <h3>Team invitations</h3>
    <p className="muted">Links are single-use and expire in 24 hours. A recipient email restricts access to that verified Google/GitHub email. No invitation email is sent automatically.</p>
    <label>Invitee email (recommended; optional)
      <input aria-label="Invitee email" value={email} maxLength={254} type="email" placeholder="developer@example.com" onChange={e=>setEmail(e.target.value)}/>
    </label>
    <button disabled={busy} onClick={create}>Create invitation link</button>
    {link && <><label>New invitation link (shown only once)
      <input aria-label="New invitation link" readOnly value={link} onFocus={e=>e.currentTarget.select()}/>
    </label><button className="outline" onClick={copyLink}>Copy invitation link</button></>}
    {notice && <p role="status">{notice}</p>}
    {error && <p role="alert">{error}</p>}
    <h4>Active invitations</h4>
    {pending.length === 0 ? <p className="muted">No pending invitations.</p> :
      pending.map(invite => <article key={invite.id}>
        <p>{invite.recipient_restricted ? 'Restricted to a verified email' : 'Unrestricted invitation'} · Expires {new Date(invite.expires * 1000).toLocaleString()}</p>
        <button className="outline" disabled={busy} onClick={()=>perform(async()=>{
          await deleteJSON(`/api/workspaces/${encodeURIComponent(workspaceId)}/invitations/${invite.id}`);
          setLink(''); setNotice('Invitation revoked.');
        })}>Revoke invitation</button>
      </article>)}
  </section>;
}
