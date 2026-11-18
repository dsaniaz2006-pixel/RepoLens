"""Resumable full AI reports, explicit human review, then public publication."""
import hashlib,json,time,os,re
from pathlib import Path

def atomic_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);pending=path.with_suffix('.tmp');pending.write_text(json.dumps(value,indent=2),encoding='utf-8');pending.replace(path)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def slug(repo):
    from backend.github.github_client import parse_github_url
    owner,name=parse_github_url('https://github.com/'+repo);return owner+'-'+name

def state_path(root,repo):return Path(root)/'.repolens_gallery'/slug(repo)/'state.json'
def read_state(root,repo):
    path=state_path(root,repo)
    return json.loads(path.read_text()) if path.exists() else {'repository':repo,'status':'not_generated'}
def valid_generated(root,repo,state):
    path=state_path(root,repo).parent/'report.md'
    return path.exists() and state.get('report_sha256')==digest(path)

def generate_ai_reports(root,repositories,*,force=False,generator=None):
    from backend.services.pipeline import generate_report
    from scripts.evaluate_repositories import audit_result
    from backend.core.config import GEMINI_MODEL
    from backend.ai.model_provider import provider
    from backend.github.github_client import _looks_like_secret_content
    root=Path(root);results=[];model=os.getenv('OLLAMA_MODEL','llama3.2') if provider()=='ollama' else GEMINI_MODEL
    for repo in repositories:
        path=state_path(root,repo);folder=path.parent;old=read_state(root,repo)
        if not force and old.get('status') in {'generated','approved'} and old.get('model')==model and old.get('provider')==provider() and valid_generated(root,repo,old):
            results.append(dict(old,resumed=True));continue
        try:
            data=(generator or generate_report)('https://github.com/'+repo,output_dir=str(folder),overwrite=True,capture_evidence=True)
            checks=audit_result(data)
            if not checks['passed'] or not checks['source_manifest_available']:raise ValueError('Report failed structural evidence validation')
            if not re.fullmatch('[0-9a-fA-F]{40}',data.get('revision','')):raise ValueError('Missing pinned commit')
            source=Path(data['report_path'])
            body=source.read_text(encoding='utf-8')
            if _looks_like_secret_content(body):raise ValueError('Possible secret in model output')
            # Public output includes source links at the exact analyzed commit.
            from urllib.parse import quote
            links='\n'.join('- ['+p+'](https://github.com/'+repo+'/blob/'+data['revision']+'/'+quote(p,safe='/')+')' for p in data['evidence_paths'])
            report=folder/'report.md';report.parent.mkdir(parents=True,exist_ok=True)
            report.write_text('# AI repository architecture report\n\nRepository: '+repo+'\n\nCommit: '+data['revision']+'\n\n'+body+'\n\n## Source evidence at this commit\n\n'+links+'\n',encoding='utf-8')
            state={'repository':repo,'status':'generated','provider':provider(),'model':model,'revision':data['revision'],'generated_at':time.time(),
                   'report_sha256':digest(report),'structural_checks':checks,'manual_review':'pending'}
        except Exception as exc:
            # A failed forced refresh must not delete a previously approved,
            # unchanged artifact. A reviewer may explicitly regenerate/review
            # a newer revision later. Never persist SDK exception text.
            if old.get('status')=='approved' and valid_generated(root,repo,old):
                state=dict(old,last_attempt_error=type(exc).__name__,last_attempt_at=time.time())
            else:
                state={'repository':repo,'status':'failed','error_type':type(exc).__name__,'attempted_at':time.time(),'manual_review':'pending'}
        atomic_json(path,state);results.append(state)
    return results

def approve(root,repo,reviewer):
    if not isinstance(reviewer,str) or not reviewer.strip() or len(reviewer)>100:raise ValueError('Provide a reviewer name after inspecting the report and source links')
    state=read_state(root,repo)
    if state.get('status') not in {'generated','approved'} or not valid_generated(root,repo,state):raise ValueError('Generate an intact report before approving it')
    state.update(status='approved',manual_review='approved',reviewer=reviewer.strip(),reviewed_at=time.time())
    atomic_json(state_path(root,repo),state);return state

def publication_receipt(root, repo, manifest):
    """Check a public artifact and its signed-off review metadata.

    Local staging, when present, can invalidate a stale public receipt. A
    distributed static release need not include private staging files.
    """
    record=manifest.get(repo)
    if not isinstance(record,dict) or record.get('type')!='reviewed_ai_report':
        return False
    if not all(record.get(key) for key in ('reviewer','reviewed_at','revision','model','provider','report_sha256')):
        return False
    if not re.fullmatch('[a-fA-F0-9]{40}',str(record['revision'])):
        return False
    path=Path(root)/'frontend/public/reports'/(slug(repo)+'-report.md')
    if not path.is_file() or digest(path)!=record['report_sha256']:
        return False
    staged=state_path(root,repo)
    if staged.exists():
        state=read_state(root,repo)
        if state.get('status')!='approved' or state.get('manual_review')!='approved':
            return False
        if not valid_generated(root,repo,state) or state.get('report_sha256')!=record['report_sha256']:
            return False
    return True


def publish(root,repositories):
    """Publish approved reports and revoke stale, changed or withdrawn reports.

    Publishing is idempotent and never promotes an unapproved source snapshot.
    The public manifest contains metadata only, never source/evidence caches.
    """
    from backend.github.github_client import _looks_like_secret_content
    root=Path(root);public=root/'frontend/public/reports';public.mkdir(parents=True,exist_ok=True)
    manifest_path=public/'gallery-manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    if not isinstance(manifest,dict):raise ValueError('Invalid gallery manifest')
    published=[]
    for repo in repositories:
        state=read_state(root,repo)
        target=public/(slug(repo)+'-report.md')
        # If a reviewer-approved artifact changed, fail loudly rather than
        # silently publishing or revoking it. It needs a fresh source review.
        if state.get('status')=='approved' and not valid_generated(root,repo,state):
            raise ValueError('Reviewed report changed; regenerate/review before publication')
        # An explicitly republished repository is taken down when review is
        # withdrawn; do not keep obsolete review receipts or public Markdown.
        if state.get('status')!='approved':
            manifest.pop(repo,None)
            target.unlink(missing_ok=True)
            continue
        body=(state_path(root,repo).parent/'report.md').read_text(encoding='utf-8')
        if _looks_like_secret_content(body):raise ValueError('Possible secret in reviewed report')
        pending=target.with_suffix('.tmp');pending.write_text(body,encoding='utf-8');pending.replace(target)
        manifest[repo]={k:state[k] for k in ('provider','model','revision','generated_at','reviewer','reviewed_at','report_sha256')}
        manifest[repo]['type']='reviewed_ai_report';published.append(repo)
    # Older files can be stale even if only a subset was published. Revoke
    # invalid receipts when their local approval record exists.
    for repo in list(manifest):
        if state_path(root,repo).exists() and not publication_receipt(root,repo,manifest):
            manifest.pop(repo,None)
            (public/(slug(repo)+'-report.md')).unlink(missing_ok=True)
    atomic_json(manifest_path,manifest)
    return published


def review_packet(root,repo):
    """Build a manual source-review checklist; this does NOT approve a report."""
    root=Path(root);state=read_state(root,repo)
    if state.get('status') not in ('generated','approved') or not valid_generated(root,repo,state):
        raise ValueError('Generate a complete report before beginning review')
    folder=state_path(root,repo).parent
    report=folder/'report.md'
    packet=folder/'REVIEW_CHECKLIST.md'
    items=[
        '# Manual source review — '+repo,
        '',
        'Report to inspect: `'+str(report.name)+'`',
        'Pinned revision: `'+state['revision']+'`',
        'Expected report SHA-256: `'+state['report_sha256']+'`',
        '',
        'Human reviewer must verify each item against source at the pinned commit:',
        '- [ ] Project summary, technologies and important entry points are accurate',
        '- [ ] Reading path, architecture and code-flow claims have supporting source evidence',
        '- [ ] Every claimed file path exists in the pinned repository revision',
        '- [ ] GitHub links point to the exact commit and relevant lines',
        '- [ ] Uncertain, inferred and unsupported claims are clearly labelled',
        '- [ ] No sensitive data, untrusted markup, private repository data or fabricated evidence',
        '- [ ] Report limitations and source-selection coverage are stated',
        '',
        'Only approve after all items have been checked manually.',
        'Command: `python scripts/prebuild_gallery.py --approve '+repo+' --reviewer "YOUR REVIEWER NAME" --acknowledge-source-review`',
    ]
    packet.write_text('\n'.join(items)+'\n',encoding='utf-8')
    return packet
