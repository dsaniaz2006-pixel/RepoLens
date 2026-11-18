// Pure, testable presentation helpers; never construct source links from an
// unverified repository, revision or citation path.
export function questionNumber(message, index) {
  const position=Number.isSafeInteger(message?.position)&&message.position>0
    ?message.position:index+1;
  return Math.max(1,Math.ceil(position/2));
}

export function pinnedCitationUrl(repository, revision, citation) {
  if (typeof repository!=='string' || !/^[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+$/.test(repository)) return null;
  const [owner,name]=repository.split('/');
  if (!/^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$/.test(owner) || name==='.' || name==='..') return null;
  if (typeof revision!=='string' || !/^[a-fA-F0-9]{40}$/.test(revision)) return null;
  const path=citation?.path;
  if (typeof path!=='string'||path.length>1000||!path||path.startsWith('/')||path.endsWith('/') || /[\x00-\x1f\x7f?#]/.test(path)) return null;
  const segments=path.split('/');
  if(segments.some(s=>!s||s==='.'||s==='..')) return null;
  const start=citation?.start_line, end=citation?.end_line;
  if (!Number.isSafeInteger(start)||!Number.isSafeInteger(end)||start<1||end<start) return null;
  return `https://github.com/${repository}/blob/${revision}/${segments.map(encodeURIComponent).join('/')}#L${start}-L${end}`;
}
