"""Static source symbol extraction for JavaScript/TypeScript and Go.

Python-only analysis does not need Tree-sitter. Missing native language
parsers are reported as unresolved source evidence instead of aborting an
otherwise valid report; they must be installed for non-Python flow edges.
"""
from importlib import import_module
from pathlib import PurePosixPath


# (package, language factory, graph language) for each supported extension.
_GRAMMARS = {
    '.js': ('tree_sitter_javascript', 'language', 'js'),
    '.jsx': ('tree_sitter_javascript', 'language', 'js'),
    '.ts': ('tree_sitter_typescript', 'language_typescript', 'js'),
    '.tsx': ('tree_sitter_typescript', 'language_tsx', 'js'),
    '.go': ('tree_sitter_go', 'language', 'go'),
}


def extract(records):
    relevant = [r for r in records
                if PurePosixPath(r['path']).suffix in _GRAMMARS
                and r.get('content') and not r.get('skipped')]
    symbols, imports, unresolved = [], {}, []
    if not relevant:
        return symbols, imports, unresolved

    try:
        from tree_sitter import Language, Parser
    except ImportError as exc:
        # Do not mislabel unavailable parsers as successful analysis.
        return symbols, imports, [
            f"{r['path']}: source-flow parser unavailable ({exc}); "
            'install the Tree-sitter packages from requirements.txt'
            for r in relevant
        ]

    specs = {}
    for suffix in {PurePosixPath(r['path']).suffix for r in relevant}:
        module_name, factory_name, language = _GRAMMARS[suffix]
        try:
            module = import_module(module_name)
            specs[suffix] = (getattr(module, factory_name), language)
        except (ImportError, AttributeError) as exc:
            unresolved.extend(
                f"{r['path']}: source-flow grammar unavailable ({exc}); "
                'install the Tree-sitter packages from requirements.txt'
                for r in relevant if PurePosixPath(r['path']).suffix == suffix
            )
    def walk(n):
        yield n
        for child in n.named_children:yield from walk(child)
    for r in relevant:
        path=r['path'];suffix=PurePosixPath(path).suffix
        if suffix not in specs:continue
        factory,language=specs[suffix];raw=r['content'].encode();root=Parser(Language(factory())).parse(raw).root_node
        text=lambda n:raw[n.start_byte:n.end_byte].decode() if n else ''
        if root.has_error:unresolved.append(path+': syntax errors; no confirmed links');continue
        mapping={}
        for n in root.named_children:
            if language=='js' and n.type=='import_statement':
                source=text(n.child_by_field_name('source')).strip('"\'')
                for child in walk(n):
                    if child.type=='import_specifier':
                        name=text(child.child_by_field_name('name'));alias=text(child.child_by_field_name('alias')) or name
                        mapping[alias]=(source,name)
            if language=='go' and n.type=='import_declaration':
                for child in walk(n):
                    if child.type=='import_spec':
                        source=text(child.child_by_field_name('path')).strip('"');alias=text(child.child_by_field_name('name')) or source.rsplit('/',1)[-1]
                        mapping[alias]=(source,None)
        imports[path]=mapping
        for n in walk(root):
            if n.type not in {'function_declaration','generator_function_declaration','method_definition','method_declaration','arrow_function','function_expression'}:continue
            name_node=n.child_by_field_name('name');name=text(name_node)
            if not name and n.parent and n.parent.type=='variable_declarator':name=text(n.parent.child_by_field_name('name'))
            if not name:continue
            # Nested functions carry their own lexical scope; no cross-scope confirmation.
            parent=n.parent;is_nested=False
            while parent:
                if parent.type in {'function_declaration','method_definition','arrow_function','function_expression','method_declaration'}:is_nested=True;break
                parent=parent.parent
            if is_nested:continue
            calls=[]
            def visit(current):
                for child in current.named_children:
                    if child.type in {'function_declaration','method_definition','arrow_function','function_expression'}:continue
                    if child.type in {'call_expression','call_expression'}:
                        fn=child.child_by_field_name('function');value=text(fn)
                        if value:calls.append((value,child.start_point.row+1,text(child).splitlines()[0][:300]))
                    visit(child)
            visit(n)
            symbols.append({'path':path,'name':name,'line':n.start_point.row+1,'calls':calls,'language':language,'method':n.type in {'method_definition','method_declaration'}})
    return symbols,imports,unresolved
