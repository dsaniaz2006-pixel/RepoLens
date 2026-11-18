"""Conservative Python AST flow evidence; no repository code is executed."""
import ast,re

def trace(records):
    from pathlib import PurePosixPath
    import posixpath
    functions={};trees={};edges=[];aliases={};unresolved=[];routes=[]
    for r in records:
        path=r['path']
        if not path.endswith('.py') or r.get('skipped'):continue
        try:tree=ast.parse(r.get('content',''))
        except SyntaxError:unresolved.append(path+': syntax error');continue
        trees[path]=(tree,r['content'].splitlines());aliases[path]={}
        for node in tree.body:
            if isinstance(node,ast.Import):
                for n in node.names:aliases[path][n.asname or n.name.split('.')[0]]=(n.name.replace('.','/'),None)
            elif isinstance(node,ast.ImportFrom):
                base=str(PurePosixPath(path).parent)
                for _ in range(max(0,node.level-1)):base=posixpath.dirname(base)
                module=posixpath.join(base,(node.module or '').replace('.','/')) if node.level else (node.module or '').replace('.','/')
                for n in node.names:aliases[path][n.asname or n.name]=(module,n.name)
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):functions[(path,node.name)]=node
            elif isinstance(node,ast.ClassDef):
                for fn in node.body:
                    if isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)):functions[(path,node.name+'.'+fn.name)]=fn
    # A literal HTTP decorator proves that the handler is declared for that
    # route. It does NOT prove the router is mounted or a request executes it.
    for (path,name),fn in functions.items():
        for decorator in fn.decorator_list:
            if not isinstance(decorator,ast.Call) or not isinstance(decorator.func,ast.Attribute):
                continue
            verb=decorator.func.attr.lower()
            if verb not in {'route','api_route','get','post','put','patch','delete','head','options'}:
                continue
            if not decorator.args or not isinstance(decorator.args[0],ast.Constant):
                continue
            url=decorator.args[0].value
            if not isinstance(url,str) or not url.startswith('/') or len(url)>160:
                continue
            # Only syntax of commonly used route decorators is interpreted.
            label='route['+('ANY' if verb in ('route','api_route') else verb.upper())+' '+url+']'
            routes.append({'from':label,'to':path+':'+name,'link_type':'CONFIRMED',
                'path':path,'line':decorator.lineno,
                'snippet':trees[path][1][decorator.lineno-1].strip(),
                'target_path':path,'target_line':fn.lineno})
    def resolve_module(module):
        return next((p for p in (module+'.py',module+'/__init__.py') if p in trees),None)
    def calls(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef,ast.Lambda)):continue
            if isinstance(child,ast.Call):yield child
            yield from calls(child)
    for (path,name),fn in functions.items():
        local_names={a.arg for a in fn.args.args}|{n.id for n in ast.walk(fn) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store)}
        for call in calls(fn):
            target=ast.unparse(call.func);dest=None;kind='INFERRED'
            if isinstance(call.func,ast.Name) and target not in local_names:
                if (path,target) in functions:dest=(path,target);kind='CONFIRMED'
                elif target in aliases[path]:
                    module,original=aliases[path][target];dest=(resolve_module(module),original)
                    if dest in functions:kind='CONFIRMED'
            elif isinstance(call.func,ast.Attribute):
                left=ast.unparse(call.func.value)
                if left in {'self','cls'} and '.' in name:dest=(path,name.rsplit('.',1)[0]+'.'+call.func.attr);kind='CONFIRMED'
                elif left in aliases[path] and left not in local_names:
                    module,original=aliases[path][left];dest=(resolve_module(module),(original+'.' if original else '')+call.func.attr);kind='CONFIRMED'
                elif (path,target) in functions and target.split('.')[0] not in local_names:dest=(path,target);kind='CONFIRMED'
            if dest not in functions:
                candidates=[key for key in functions if key[1]==target]
                if len(candidates)==1 and target not in local_names:dest=candidates[0];kind='INFERRED'
                else:unresolved.append(path+':'+str(call.lineno)+': '+target);continue
            if dest==(path,name):continue
            edges.append({'from':path+':'+name,'to':dest[0]+':'+dest[1], 'link_type':kind,'path':path,'line':call.lineno,'snippet':trees[path][1][call.lineno-1].strip(),'target_path':dest[0],'target_line':functions[dest].lineno})
    from backend.services.flow_symbols import extract
    symbols,imports,extra=extract(records);unresolved.extend(extra)
    by_name={}
    for symbol in symbols:by_name.setdefault(symbol['name'],[]).append(symbol)
    for symbol in symbols:
        for target,line,snippet in symbol['calls']:
            matches=by_name.get(target,[]);kind='INFERRED'
            same=[x for x in matches if x['path']==symbol['path'] and not x['method']]
            # JavaScript/Go call resolution remains conservative without type inference.
            if len(same)==1 and not symbol['method']:dest=same[0]
            else:
                reference=imports.get(symbol['path'],{}).get(target)
                if reference and reference[0].startswith('.'):
                    base=posixpath.normpath(posixpath.join(posixpath.dirname(symbol['path']),reference[0]))
                    matches=[x for x in symbols if x['name']==reference[1] and x['path'] in {base+ext for ext in ('.js','.jsx','.ts','.tsx','/index.js','/index.ts')}]
                if len(matches)!=1:unresolved.append(symbol['path']+':'+str(line)+': '+target);continue
                dest=matches[0]
            if dest==symbol:continue
            edges.append({'from':symbol['path']+':'+symbol['name'],'to':dest['path']+':'+dest['name'],'link_type':kind,'path':symbol['path'],'line':line,'snippet':snippet,'target_path':dest['path'],'target_line':dest['line']})
    edges.extend(routes)
    # One bounded representative path, rather than an unreadable whole-program graph.
    starts=sorted({e['from'] for e in edges},key=lambda x:(not x.startswith('route['),not x.endswith(':main'),-sum(e['from']==x for e in edges),x))
    chosen=[];seen=set();current=starts[0] if starts else None
    while current and len(chosen)<8:
        options=[e for e in edges if e['from']==current and e['to'] not in seen]
        if not options:break
        edge=options[0];chosen.append(edge);seen.add(current);current=edge['to']
    nodes=list(dict.fromkeys(v for e in chosen for v in (e['from'],e['to'])))
    ids={name:'n'+str(i) for i,name in enumerate(nodes)}
    safe=lambda s:re.sub(r'[^\w /.:()-]','_',s)[:160]
    lines=['flowchart TD']+[f'  {ids[n]}["{safe(n)}"]' for n in nodes]
    for e in chosen:lines.append(f"  {ids[e['from']]} {'-->|CONFIRMED|' if e['link_type']=='CONFIRMED' else '-.->|INFERRED|'} {ids[e['to']]}")
    return {'edges':chosen,'mermaid':'\n'.join(lines),'confidence':'partial' if chosen else 'low',
        'unresolved':unresolved[:100], 'limits':['Static Python, JavaScript/TypeScript and Go evidence only. Python imports/aliases and class methods are resolved where unambiguous; JS/TS/Go candidates are inferred. Dynamic behavior is never claimed complete. CONFIRMED means a statically resolved call, not executed behavior.']}

def markdown(flow):
    return '\n\n## Source-traced flow\n\n```mermaid\n'+flow['mermaid']+'\n```\n\n| From | To | Evidence | Link |\n|---|---|---|---|\n'+''.join('| '+e['from'].replace('|','_')+' | '+e['to'].replace('|','_')+' | '+e['path'].replace('|','_')+':'+str(e['line'])+' | '+e['link_type']+' |\n' for e in flow['edges'])+'\n'+' '.join(flow['limits'])
