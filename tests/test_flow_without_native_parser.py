"""Regression tests: Python flow must not require unrelated native grammars."""

from backend.services.code_flow import trace


def test_python_flow_runs_without_tree_sitter_and_resolves_real_edges():
    result = trace([
        {'path': 'main.py', 'content': 'from helper import task\ndef main():\n    task()\n'},
        {'path': 'helper.py', 'content': 'def task():\n    return 1\n'},
    ])
    assert result['edges']
    assert result['edges'][0]['to'] == 'helper.py:task'
    assert result['edges'][0]['link_type'] == 'CONFIRMED'


def test_missing_native_grammar_is_reported_not_silently_fabricated(monkeypatch):
    """Simulate a missing native core on any machine, including macOS."""
    import builtins
    original_import = builtins.__import__

    def block_tree_sitter(name, *args, **kwargs):
        if name == 'tree_sitter':
            raise ModuleNotFoundError("No module named 'tree_sitter'", name=name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', block_tree_sitter)
    result = trace([{'path': 'main.js',
                     'content': 'function main() { helper(); }\nfunction helper() { return 1; }'}])
    assert result['edges'] == []
    assert any('parser unavailable' in message and 'requirements.txt' in message
               for message in result['unresolved'])
