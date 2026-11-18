"""Transitive graphs from recorded resolution artifacts, without running repo code."""
import json,re,tomllib,hashlib
from packaging.requirements import Requirement,InvalidRequirement
from packaging.utils import canonicalize_name
from packaging.markers import default_environment

def graphs(records):
    nodes=[];edges=[];limits=[]
    for record in records:
        path=record['path'];content=record.get('content','');prefix=path+':'
        try:
            if path.endswith('repolens-pip-inspect.json'):
                data=json.loads(content);installed=data.get('installed',[])
                selected={canonicalize_name(p['metadata']['name']):p for p in installed}
                env={**data.get('environment',{}),'extra':''}
                has_environment=bool(data.get('environment'))
                if not has_environment:limits.append(path+': exported environment missing; marker activation is unknown')
                for name,p in selected.items():nodes.append({'id':prefix+name,'name':name,'version':p['metadata']['version'],'manifest':path,'ecosystem':'pip'})
                for name,p in selected.items():
                    for raw in p['metadata'].get('requires_dist',[]):
                        try:req=Requirement(raw)
                        except InvalidRequirement:limits.append('Unsupported Python dependency specifier');continue
                        target=canonicalize_name(req.name);active=(not req.marker or req.marker.evaluate(env)) if has_environment else (None if req.marker else True)
                        edges.append({'from':prefix+name,'to':prefix+target if target in selected else None,'dependency':target,'constraint':str(req.specifier),'active':active,'marker':str(req.marker) if req.marker else None})
                limits.append(path+': graph reflects the exported environment; optional extra selection is not reconstructed')
            elif path.endswith(('uv.lock','poetry.lock')):
                data=tomllib.loads(content);packages=data.get('package',[]);lookup={};identities={}
                counts={}
                for p in packages:
                    key=canonicalize_name(p['name'])+'@'+p['version'];counts[key]=counts.get(key,0)+1
                for p in packages:
                    name=canonicalize_name(p['name']);key=name+'@'+p['version'];identity=prefix+key
                    if counts[key]>1:identity+=':'+hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()[:12]
                    identities[id(p)]=identity;lookup.setdefault(name,[]).append((identity,p))
                    nodes.append({'id':identity,'name':name,'version':p['version'],'manifest':path,'ecosystem':'pip'})
                for p in packages:
                    source=identities[id(p)];dependencies=p.get('dependencies',[])
                    if isinstance(dependencies,dict):dependencies=[{'name':name,'constraint':str(value)} for name,value in dependencies.items()]
                    for dep in dependencies:
                        if isinstance(dep,str):dep={'name':dep}
                        name=canonicalize_name(dep['name']);matches=lookup.get(name,[])
                        if dep.get('version'):matches=[x for x in matches if x[1]['version']==dep['version']]
                        for target,_ in matches:edges.append({'from':source,'to':target,'dependency':name,'constraint':dep.get('constraint',dep.get('version','')),'marker':dep.get('marker'),'active':None})
                        if not matches:edges.append({'from':source,'to':None,'dependency':name,'constraint':dep.get('version',''),'active':None})
                limits.append(path+': lockfile graph includes platform/optional variants; it is not an installed-environment assertion')
            elif path.endswith('repolens-go-graph.txt'):
                names=set()
                for line in content.splitlines():
                    parts=line.split()
                    if len(parts)!=2 or any(not re.fullmatch(r'[A-Za-z0-9_./!+@-]+',p) for p in parts):continue
                    source,target=parts;names.update(parts)
                    edges.append({'from':prefix+source,'to':prefix+target,'dependency':target.rsplit('@',1)[0],'constraint':target.rsplit('@',1)[-1] if '@' in target else ''})
                for value in sorted(names):
                    name,sep,version=value.rpartition('@');nodes.append({'id':prefix+value,'name':name if sep else value,'version':version if sep else None,'manifest':path,'ecosystem':'go'})
                limits.append(path+': Go module requirement graph; multiple requested module versions can appear before minimal-version selection')
        except (ValueError,TypeError,KeyError,AttributeError):limits.append(path+': invalid dependency resolution artifact')
    if len(nodes)>10000 or len(edges)>30000:raise ValueError('Dependency graph exceeds supported bounds')
    return {'nodes':nodes,'edges':edges,'limits':limits}
