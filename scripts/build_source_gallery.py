"""Generate twenty reproducible source snapshots from public GitHub evidence.

No model credential is used. Cached evidence enables deterministic offline rebuilds.
"""
import sys,json,re,ast,hashlib,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.github.github_client import _looks_like_secret_content
from prebuild_gallery import ROOT,REPOSITORIES,build
SOURCES=['src/flask/app.py','fastapi/applications.py','django/core/handlers/base.py','lib/core/Axios.js','packages/vite/src/node/index.ts','src/requests/sessions.py','httpx/_client.py','pydantic/main.py','lib/sqlalchemy/engine/base.py','src/markupsafe/__init__.py','packages/runtime-core/src/index.ts','packages/react/src/ReactClient.js','lib/application.js','actionpack/lib/action_controller/base.rb','packages/svelte/src/internal/client/index.js','src/_pytest/config/__init__.py','typer/main.py','src/click/core.py','starlette/applications.py','crates/ruff/src/lib.rs']
CACHE=ROOT/'evaluation/gallery-evidence'

def get(url):
    response=requests.get(url,headers={'User-Agent':'RepoLens-public-gallery','Accept':'application/vnd.github+json'},timeout=30)
    response.raise_for_status()
    if len(response.content)>1000000:raise ValueError('Gallery source exceeds limit')
    return response

def generate(pair):
    repo,path=pair;slug=repo.replace('/','-');cache=CACHE/(slug+'.json')
    if cache.exists():evidence=json.loads(cache.read_text())
    else:
        metadata=get('https://api.github.com/repos/'+repo).json()
        sha=get('https://api.github.com/repos/'+repo+'/commits/'+quote(metadata['default_branch'],safe='')).json()['sha']
        base='https://raw.githubusercontent.com/'+repo+'/'+sha+'/'
        source=get(base+path).text
        if _looks_like_secret_content(source):raise ValueError('Possible secret in gallery source')
        evidence={'repository':repo,'revision':sha,'description':metadata.get('description') or '', 'language':metadata.get('language') or '', 'source_path':path,'source':source,'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'retrieved_at':time.time(),'method':'public_source_snapshot'}
        CACHE.mkdir(parents=True,exist_ok=True);cache.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    source=evidence['source'];lines=source.splitlines();symbols=[]
    if path.endswith('.py'):
        tree=ast.parse(source)
        for n in ast.walk(tree):
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):symbols.append((n.lineno,n.name,type(n).__name__))
    else:
        from tree_sitter import Language,Parser
        import tree_sitter_javascript,tree_sitter_typescript,tree_sitter_go,tree_sitter_rust,tree_sitter_ruby
        suffix=Path(path).suffix
        factories={'.js':tree_sitter_javascript.language,'.ts':tree_sitter_typescript.language_typescript,'.go':tree_sitter_go.language,'.rs':tree_sitter_rust.language,'.rb':tree_sitter_ruby.language}
        parser=Parser(Language(factories[suffix]()))
        root=parser.parse(source.encode()).root_node
        def visit(node):
            if node.type in {'function_declaration','method_definition','class_declaration','function_item','class','method','singleton_method','method_declaration','export_specifier'} and not node.has_error:
                name=node.child_by_field_name('name')
                if name:symbols.append((node.start_point.row+1,name.text.decode(),node.type))
            if node.type=='export_statement' and not node.has_error and not any(c.type=='export_clause' for c in node.named_children):
                symbols.append((node.start_point.row+1,'module export','export statement'))
            if node.type=='assignment_expression':
                right=node.child_by_field_name('right');left=node.child_by_field_name('left')
                if right and left and right.type=='function_expression' and not node.has_error:symbols.append((node.start_point.row+1,left.text.decode(),'function assignment'))
            for child in node.named_children:visit(child)
        visit(root)
    sha=evidence['revision'];blob=f'https://github.com/{repo}/blob/{sha}/{path}'
    text=f'# {repo}: source-backed codebase snapshot\n\n'
    text+='Generation method: deterministic public-source inspection, not an AI architecture analysis.\n\n'
    text+=f'Commit: `{sha}`\n\nRepository description (GitHub metadata): {evidence["description"]}\n\nPrimary language reported by GitHub: {evidence["language"]}.\n\n'
    text+=f'## Start with this source file\n\n[{path}]({blob}#L1-L{min(40,len(lines))}) contains {len(lines)} lines in this snapshot. Read its module header and imports before following the symbols below.\n\n'
    text+='## Verified declarations and reading path\n\n'
    for line,name,kind in sorted(symbols)[:16]:text+=f'- [{name}]({blob}#L{line}) — {kind} declared at line {line}. Inspect its implementation and callers; no runtime behavior is inferred from the name.\n'
    if not symbols:text+='No supported declaration was extracted. Use the cited source directly.\n'
    text+='\n## Suggested onboarding investigation\n\n1. Read the cited module header and imports.\n2. Choose one declaration above and inspect its callers and tests in the same commit.\n3. Record inputs, return values, and error paths with source references.\n\n'
    text+='## Limits\n\nThis report inspects one real source file; it does not establish the complete architecture, dependency graph, runtime call flow, security, or test coverage. Use Analyze Repo for an AI report and the source tracer for supported call evidence. The snapshot may be stale after the pinned commit.\n'
    text+=f'\nEvidence checksum: `{evidence["source_sha256"]}`.\n'
    reports=ROOT/'frontend/public/reports';reports.mkdir(parents=True,exist_ok=True)
    (reports/(slug+'-report.md')).write_text(text,encoding='utf-8')
    return repo,len(symbols)

if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=4) as pool:
        for repo,count in pool.map(generate,zip(REPOSITORIES,SOURCES)):print(repo,':',count,'source declarations',flush=True)
    build()
