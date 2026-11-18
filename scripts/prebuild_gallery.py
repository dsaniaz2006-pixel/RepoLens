"""Build public HTML from explicitly curated reports; generation requires --generate."""
import argparse,html,json,sys,re
from urllib.parse import urlparse,unquote
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
ROOT=Path(__file__).resolve().parents[1]
from dotenv import load_dotenv
load_dotenv(ROOT/'.env')
REPOSITORIES=['pallets/flask','fastapi/fastapi','django/django','axios/axios','vitejs/vite','psf/requests','encode/httpx','pydantic/pydantic','sqlalchemy/sqlalchemy','pallets/markupsafe','vuejs/core','facebook/react','expressjs/express','rails/rails','sveltejs/svelte','pytest-dev/pytest','tiangolo/typer','pallets/click','encode/starlette','astral-sh/ruff']


def render_report(markdown):
    """Escape all report text; render only bounded Markdown and GitHub source links.

    Model output is untrusted. Never render user/model HTML, JavaScript URLs,
    inline event handlers, or raw HTML from a repository.
    """
    def inline(text):
        escaped=html.escape(text,quote=True)
        def source_link(match):
            label=html.escape(html.unescape(match.group(1)),quote=True)
            url=html.unescape(match.group(2))
            parts=urlparse(url)
            if parts.scheme!='https' or parts.hostname!='github.com' or parts.username or parts.password:
                return match.group(0)
            return '<a href="'+html.escape(url,quote=True)+'" rel="noopener noreferrer">'+label+'</a>'
        return re.sub(r'\[([^\]\n]{1,200})\]\((https://github\.com/[^\s)\n]{1,600})\)',source_link,escaped)
    lines=[];fenced=False;listed=False
    for line in markdown.splitlines():
        if line.lstrip().startswith('```'):
            if listed:lines.append('</ul>');listed=False
            lines.append('</code></pre>' if fenced else '<pre><code>')
            fenced=not fenced
            continue
        if fenced:
            lines.append(html.escape(line,quote=True)+'\n')
            continue
        if not line.strip():
            if listed:lines.append('</ul>');listed=False
            continue
        heading=re.match(r'^(#{1,4})\s+(.*)$',line)
        if heading:
            if listed:lines.append('</ul>');listed=False
            size=len(heading.group(1))
            lines.append(f'<h{size}>'+inline(heading.group(2))+f'</h{size}>')
        elif re.match(r'^\s*[-*]\s+',line):
            if not listed:lines.append('<ul>');listed=True
            lines.append('<li>'+inline(re.sub(r'^\s*[-*]\s+','',line))+'</li>')
        else:
            if listed:lines.append('</ul>');listed=False
            lines.append('<p>'+inline(line)+'</p>')
    if fenced:lines.append('</code></pre>')
    if listed:lines.append('</ul>')
    return '<section class="report-body">'+''.join(lines)+'</section>'

def build(generate=False, *, min_reviewed=None):
    """Build an anonymous gallery with honest review status and safe HTML."""
    reports=ROOT/'frontend/public/reports'
    if generate:
        from backend.services.gallery_pipeline import generate_ai_reports
        for result in generate_ai_reports(ROOT,REPOSITORIES):
            print(result['repository'],result['status'])
    out=ROOT/'frontend/gallery';out.mkdir(parents=True,exist_ok=True)
    public=ROOT/'frontend/public/gallery';public.mkdir(parents=True,exist_ok=True)
    manifest_path=reports/'gallery-manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    from backend.services.gallery_pipeline import publication_receipt
    if not isinstance(manifest,dict):raise ValueError('Invalid gallery publication receipt')
    cards=[];reviewed_count=0
    for repo in REPOSITORIES:
        slug=repo.replace('/','-')
        matches=[reports/(slug+'-report.md'),reports/(slug+'-analysis.md')]
        path=next((f for f in matches if f.is_file()),None)
        if not path:continue
        content=path.read_text(encoding='utf-8')
        from backend.github.github_client import _looks_like_secret_content
        if _looks_like_secret_content(content):
            raise ValueError('Possible secret in gallery input; review before publishing')
        reviewed=bool(publication_receipt(ROOT,repo,manifest))
        reviewed_count+=int(reviewed)
        title=html.escape(repo,quote=True)
        label='Reviewed AI architecture report' if reviewed else 'Source snapshot — AI review pending'
        caution=('This report was reviewed against its pinned source revision. Always verify before acting.' if reviewed
                 else 'This is a source snapshot, not an AI architecture analysis or a completed review.')
        page=f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Source-evidence report for {title}. Review status is explicitly labelled."><title>{title} codebase report — RepoLens</title><link rel="icon" href="/favicon.svg"><link rel="stylesheet" href="/gallery/gallery.css"></head><body><div class="shell"><header class="top"><a class="brand" href="/gallery/"><img src="/favicon.svg" width="36" height="36" alt="">RepoLens <span>Public Gallery</span></a><nav aria-label="Gallery navigation"><a href="/gallery/">All reports</a><a href="/dashboard/">Dashboard</a></nav></header><section class="hero"><span class="eyebrow">REPOSITORY REPORT</span><h1>{title}</h1><p class="review-status {'reviewed' if reviewed else 'unreviewed'}">{html.escape(label)}</p><p>{html.escape(caution)}</p><div class="actions"><a class="cta" href="/dashboard/">Try on your repo</a><button type="button" id="copy-link">Share · Copy link</button><span id="copy-status" role="status" aria-live="polite"></span></div></section><main class="report">{render_report(content)}</main><footer><a href="/gallery/">Browse all reports</a> <span>Source evidence belongs to the cited repository. Verify the pinned revision.</span></footer></div><script>document.getElementById("copy-link").onclick=async()=>{{try{{await navigator.clipboard.writeText(location.href);document.getElementById("copy-status").textContent="Link copied"}}catch{{document.getElementById("copy-status").textContent="Copy the page address from your browser"}}}};</script></body></html>"""
        target=public/slug/'index.html';target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(page,encoding='utf-8')
        cards.append(f'<article><span class="repo-icon" aria-hidden="true">&lt;/&gt;</span><div class="card-content"><h2><a href="/gallery/{slug}/index.html">{title}</a></h2><p>{html.escape(label)}</p></div><span class="card-arrow" aria-hidden="true">↗</span></article>')
    index=f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Browse verified-source public codebase snapshots and manually reviewed AI reports in RepoLens."><title>Public Codebase Gallery — RepoLens</title><link rel="icon" href="/favicon.svg"><link rel="stylesheet" href="/gallery/gallery.css"></head><body><div class="shell"><header class="top"><a class="brand" href="/gallery/"><img src="/favicon.svg" width="36" height="36" alt="">RepoLens <span>Public Gallery</span></a><nav aria-label="Gallery navigation"><a href="/dashboard/">Dashboard</a><a href="/">Home</a></nav></header><section class="hero"><span class="eyebrow">EXPLORE REAL SOURCE</span><h1>Understand a repository before you open your editor.</h1><p>Explore cached codebase reports. Every item clearly states whether a human reviewed its AI architecture analysis or it is only a source snapshot.</p><div class="summary"><strong>{len(cards)} repositories</strong><span>{reviewed_count} reviewed AI architecture reports</span><span>{len(cards)-reviewed_count} source snapshots</span></div><a class="cta" href="/dashboard/">Try on your repo</a></section><main><h2 class="section-title">Repository library</h2><div class="catalog">{''.join(cards)}</div></main><footer><span>Reports are cached at a specific commit. Do not rely on outdated evidence.</span><a href="/dashboard/">Open RepoLens dashboard</a></footer></div></body></html>"""
    (out/'index.html').write_text(index,encoding='utf-8')
    print(f'Built {len(cards)} gallery pages; {reviewed_count} reviewed AI reports; {len(REPOSITORIES)-reviewed_count} configured repositories still need full AI generation/review/publication.')
    if min_reviewed is not None and reviewed_count<min_reviewed:
        raise ValueError(f'Only {reviewed_count} of {min_reviewed} required reviewed AI reports are published; source snapshots do not count.')
def generation_batch(root, repositories, batch_size=0, *, force=False):
    """Choose pending reports before failed retries; don't starve later repos.

    Explicit --repo and --force are passed by the caller. Approved artifacts
    are never regenerated unless force=True.
    """
    from backend.services.gallery_pipeline import read_state
    if not batch_size:return list(repositories)
    if force:return list(repositories)[:batch_size]
    pending=[repo for repo in repositories if read_state(root,repo).get('status')=='not_generated']
    failed=[repo for repo in repositories if read_state(root,repo).get('status')=='failed']
    return (pending+failed)[:batch_size]

if __name__=='__main__':
    from backend.services.gallery_pipeline import generate_ai_reports,approve,publish,read_state,review_packet
    p=argparse.ArgumentParser(description=__doc__);actions=p.add_mutually_exclusive_group()
    actions.add_argument('--generate',action='store_true',help='Generate/resume full AI reports into private staging; consumes provider quota')
    actions.add_argument('--approve',metavar='OWNER/REPO',help='Approve one report after manual source review')
    actions.add_argument('--publish',action='store_true',help='Copy only intact approved AI reports into the public gallery')
    actions.add_argument('--status',action='store_true',help='Show generation/review state without contacting providers')
    actions.add_argument('--review',metavar='OWNER/REPO',help='Create a source-review checklist for a generated report')
    p.add_argument('--repo',action='append',choices=REPOSITORIES,help='Limit generation/publication to selected repositories')
    p.add_argument('--reviewer');p.add_argument('--force',action='store_true')
    p.add_argument('--acknowledge-source-review',action='store_true',help='Explicitly attest that cited source and claims were manually reviewed')
    p.add_argument('--batch-size',type=int,default=0,help='Limit live AI generation to this many selected repositories per run')
    p.add_argument('--require-reviewed',action='store_true',help='Release gate: fail until all 20 reports are reviewed AI reports')
    args=p.parse_args()
    selected=args.repo or REPOSITORIES
    if args.batch_size<0:p.error('--batch-size must be nonnegative')
    if args.generate and args.batch_size:
        selected=generation_batch(ROOT,selected,args.batch_size,force=args.force)
    if args.review:
        if args.review not in REPOSITORIES:p.error('Repository is not in the public allowlist')
        try:print('Review checklist written:',review_packet(ROOT,args.review))
        except ValueError as exc:p.error(str(exc))
        raise SystemExit(0)
    if args.generate:
        results=generate_ai_reports(ROOT,selected,force=args.force)
        for result in results:print(result['repository']+': '+result['status'])
        raise SystemExit(1 if any(r['status']=='failed' for r in results) else 0)
    if args.approve:
        if args.approve not in REPOSITORIES:p.error('Repository is not in the public allowlist')
        if not args.acknowledge_source_review:p.error('First inspect --review and confirm source review with --acknowledge-source-review')
        try:approve(ROOT,args.approve,args.reviewer)
        except ValueError as exc:p.error(str(exc))
        print('Approval saved for '+args.approve)
    elif args.publish:print('Published '+str(len(publish(ROOT,selected)))+' approved AI reports')
    elif args.status:
        counts={}
        for repo in selected:
            state=read_state(ROOT,repo);status=state.get('status','not_generated')
            counts[status]=counts.get(status,0)+1
            print(f"{repo}: {status}"+(' (reviewer: '+state['reviewer']+')' if state.get('reviewer') else ''))
        print('Status counts: '+', '.join(f'{key}={value}' for key,value in sorted(counts.items())))
        raise SystemExit(0)
    try:
        build(min_reviewed=len(REPOSITORIES) if args.require_reviewed else None)
    except ValueError as exc:
        print('Gallery release is not ready: '+str(exc),file=sys.stderr)
        raise SystemExit(2)
