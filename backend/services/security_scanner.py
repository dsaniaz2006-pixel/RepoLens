"""Bounded dependency advisory and source-pattern review; not a security certification."""
import json,re,ast
from packaging.requirements import Requirement,InvalidRequirement
from packaging.specifiers import SpecifierSet, InvalidSpecifier
from packaging.version import Version, InvalidVersion
from backend.github.github_client import _get

def parse_dependencies(records):
    deps=[];warnings=[]
    for r in records:
        path=r['path'];content=r.get('content','')
        if path.endswith('requirements.txt'):
            for line in content.splitlines():
                line=line.split(' #')[0].strip()
                if not line or line.startswith('#'):continue
                try:
                    req=Requirement(line)
                    exact=[s.version for s in req.specifier if s.operator=='==' and '*' not in s.version]
                    deps.append({'name':req.name,'ecosystem':'pip','version':exact[0] if len(exact)==1 else None,'constraint':str(req.specifier),'manifest':path,'marker':str(req.marker) if req.marker else None,'source_kind':'declared'})
                except InvalidRequirement:warnings.append(f'{path}: unsupported requirement: {line[:80]}')
        elif path.endswith('package.json'):
            try:
                data=json.loads(content)
                for section in ('dependencies','devDependencies'):
                    for name,version in data.get(section,{}).items():
                        deps.append({'name':name,'ecosystem':'npm','version':version if isinstance(version,str) and re.fullmatch(r'\d+\.\d+\.\d+(?:-[\w.-]+)?',version) else None,'constraint':str(version),'manifest':path})
            except (ValueError,AttributeError):warnings.append(path+': invalid package manifest')
        elif path.endswith('go.mod'):
            for name,version in re.findall(r'^\s*(?:require\s+)?([\w.-]+/[\w./-]+)\s+(v[^\s]+)',content,re.M):
                deps.append({'name':name,'ecosystem':'go','version':version,'constraint':version,'manifest':path})
    return deps,warnings

def patterns(records):
    findings=[]
    for r in records:
        if not r['path'].endswith('.py'):continue
        try:tree=ast.parse(r.get('content',''))
        except SyntaxError:continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            name = ast.unparse(node.func)
            issue = None

            if name in {
                "eval",
                "exec",
                "pickle.loads",
                "pickle.load",
            }:
                issue = name + " requires review of input trust"

            if name.startswith("subprocess.") and any(
                kw.arg == "shell"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value is True
                for kw in node.keywords
            ):
                issue = "Shell execution: inspect input construction"

            if name in {"open", "builtins.open"}:
                path_arg = (
                    node.args[0]
                    if node.args
                    else next(
                        (
                            kw.value
                            for kw in node.keywords
                            if kw.arg == "file"
                        ),
                        None,
                    )
                )

                if path_arg is not None and not (
                    isinstance(path_arg, ast.Constant)
                    and isinstance(path_arg.value, str)
                ):
                    issue = (
                        "Dynamic file path: review whether the path "
                        "is controlled by untrusted input"
                    )

            if issue:
                findings.append({
                    "path": r["path"],
                    "line": node.lineno,
                    "issue": issue,
                    "status": "review_required",
                })
            
    return findings


def _advisory_version_status(dep, vulnerability):
    """Check a pinned version against an explicitly parseable advisory range.

    A GHSA package match alone is not proof that a particular version is
    affected. Unsupported npm/Go syntax stays `version_unverified` instead
    of being advertised as a known vulnerability.
    """
    version=dep.get('version')
    if not version:
        return 'version_unresolved'
    expression=vulnerability.get('vulnerable_version_range')
    if not isinstance(expression,str) or not expression.strip():
        return 'version_unverified'
    try:
        if dep['ecosystem']=='pip':
            return 'affected' if Version(version) in SpecifierSet(expression) else 'not_affected'
        if dep['ecosystem'] in {'npm','go'}:
            # Do not apply PEP 440 to npm's ^, ~, ||, hyphen and wildcard
            # ranges, or to prerelease ranges with different precedence rules.
            # These must be verified by an ecosystem-specific resolver.
            normalized=expression.replace(' ', '')
            plain=version.removeprefix('v')
            if not re.fullmatch(r'\d+\.\d+\.\d+',plain):
                return 'version_unverified'
            comparators=normalized.split(',')
            if not all(re.fullmatch(r'(?:<=|>=|==|!=|<|>|=)\d+\.\d+\.\d+',part) for part in comparators):
                return 'version_unverified'
            normalized=','.join('=='+part[1:] if part.startswith('=') and not part.startswith('==') else part for part in comparators)
            return 'affected' if Version(plain) in SpecifierSet(normalized) else 'not_affected'
    except (InvalidVersion,InvalidSpecifier,ValueError,TypeError):
        return 'version_unverified'
    return 'version_unverified'

def scan(records, *, advisory_get=_get, extra_dependencies=None):
    deps,warnings=parse_dependencies(records);results=[]
    deps+=extra_dependencies or []
    deps=list({(d['ecosystem'],d['name'],d['version'],d['manifest'],d.get('marker')):d for d in deps}.values())
    for dep in deps[:60]:
        affected=dep['name']+('@'+dep['version'] if dep['version'] else '')
        try:
            advisories=advisory_get('/advisories','checking package advisories',params={'ecosystem':dep['ecosystem'],'affects':affected,'per_page':100})
            if not isinstance(advisories,list):raise ValueError()
            findings=[]
            for a in advisories:
                if a.get('withdrawn_at'):continue
                for v in a.get('vulnerabilities',[]):
                    if v.get('package',{}).get('name','').lower()==dep['name'].lower():
                        status_of_version=_advisory_version_status(dep,v)
                        if status_of_version=='not_affected':continue
                        findings.append({'id':a.get('ghsa_id'),'cve':a.get('cve_id'),'severity':a.get('severity'),'summary':a.get('summary'), 'affected_range':v.get('vulnerable_version_range'),'fixed_version':v.get('first_patched_version'),'status':status_of_version})
            status='checked' if len(advisories)<100 else 'partial'
        except Exception:findings=[];status='unavailable'
        imports=[{'path':r['path'],'line':i} for r in records for i,line in enumerate(r.get('content','').splitlines(),1) if dep['name'].replace('-','_') in line and re.search(r'\b(import|from|require)\b',line)][:50]
        results.append(dict(dep,advisories=findings,check_status=status,possible_imports=imports))
    unverified=sum(a['status'] in ('version_unverified','version_unresolved') for d in results for a in d['advisories'])
    return {'dependencies':results,'patterns':patterns(records),'warnings':warnings,
            'coverage':{'packages_discovered':len(deps),'packages_checked':len(results),'package_limit':60,
                        'advisory_complete':len(deps)<=60 and all(d['check_status']=='checked' for d in results),
                        'unverified_advisories':unverified,
                        'complete':False,'scope':'Selected files only; never a clean-security certification'},
            'limits':['Selected source files only; dependency graphs use the available resolution artifacts.','A package advisory does not prove an installed version is affected. Unknown or unsupported version ranges remain unverified.','Import matches are heuristic and may miss aliases.']+(['Dependency scan capped at 60 packages.'] if len(deps)>60 else [])}


def dependency_graph(records):
    """Resolved npm lockfile graph when available; unresolved manifests stay explicit."""
    nodes=[];edges=[];limits=[]
    for record in records:
        if not record['path'].endswith('package-lock.json'):continue
        try:
            data=json.loads(record.get('content',''));packages=data.get('packages')
            if not isinstance(packages,dict):limits.append('npm lockfile v1 dependency graph is not supported');continue
            prefix=record['path']+':'
            selected_packages=dict(list(packages.items())[:3000])
            for path,pkg in selected_packages.items():
                name=pkg.get('name') or path.rsplit('node_modules/',1)[-1] or data.get('name','root')
                nodes.append({'id':prefix+path,'name':name,'version':pkg.get('version'),'manifest':record['path'],'ecosystem':'npm'})
                for dependency,constraint in pkg.get('dependencies',{}).items():
                    location=path
                    while True:
                        candidate=(location+'/' if location else '')+'node_modules/'+dependency
                        if candidate in packages:break
                        if not location:candidate=None;break
                        location=location.rsplit('/node_modules/',1)[0] if '/node_modules/' in location else ''
                    edges.append({'from':prefix+path,'to':prefix+candidate if candidate in selected_packages else None,'dependency':dependency,'constraint':constraint})
            if len(packages)>3000:limits.append('Dependency graph capped at 3000 package nodes')
        except (ValueError,TypeError,AttributeError):limits.append('Invalid npm lockfile')
    from backend.services.dependency_graphs import graphs
    other=graphs(records);nodes.extend(other['nodes']);edges.extend(other['edges']);limits.extend(other['limits'])
    if not nodes:limits.append('No resolution artifact found. Supply package-lock.json, uv.lock, poetry.lock, repolens-pip-inspect.json or repolens-go-graph.txt to inspect transitive dependencies.')
    return {'nodes':nodes,'edges':edges,'limits':limits}


def scan_repository(data):
    from backend.github.github_client import fetch_file_content,_looks_like_secret_content
    records=list(data['records']);selection_limits=[];artifacts=0
    already={r['path'] for r in records if r.get('content') and not r.get('skipped')}
    manifests={'requirements.txt','package.json','go.mod'}
    resolution={'package-lock.json','uv.lock','poetry.lock','repolens-pip-inspect.json','repolens-go-graph.txt'}
    from backend.core.config import SKIP_DIR_NAMES
    for item in data['tree']:
        path=item.get('path','')
        if (path in already or item.get('type','blob')!='blob' or
                any(part in SKIP_DIR_NAMES or part.startswith('.') for part in path.split('/'))):
            continue
        filename=path.rsplit('/',1)[-1]
        if filename in manifests | resolution:
            limit=200000 if filename in manifests else 500000
            if item.get('size',0)>limit or artifacts>=20:
                selection_limits.append(path+': resolution artifact omitted by size/count limit');continue
            artifacts+=1
            try:content=fetch_file_content(data['owner'],data['repo'],path,data['revision'])
            except Exception:
                selection_limits.append(path+': resolution artifact unavailable');continue
            if len(content)<=limit and not _looks_like_secret_content(content):
                records.append({'path':path,'content':content});already.add(path)
            else:selection_limits.append(path+': resolution artifact omitted by size/secret filter')
    graph=dependency_graph(records)
    # Advisory checks also cover resolved transitive packages, within the displayed cap.
    result=scan(records,extra_dependencies=[{'name':n['name'],'ecosystem':n['ecosystem'],'version':n['version'],'constraint':n['version'] or '', 'manifest':n['manifest']} for n in graph['nodes'] if n.get('ecosystem') and n.get('version')])
    result['dependency_graph']=graph
    result['limits']+=selection_limits
    result['coverage'].update(tree_incomplete=bool(data.get('truncated')),resolution_artifacts_fetched=artifacts,selection_limits=selection_limits)
    result['warnings']+=['Advisory matches require version, reachability and configuration review; they do not prove exploitability.']
    return result
