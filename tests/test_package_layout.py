"""Catch flat imports and moved-resource path regressions."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_no_flat_imports_or_root_python_shims():
    modules = {p.stem for p in (ROOT / 'backend').rglob('*.py') if p.name != '__init__.py'}
    assert not list(ROOT.glob('*.py'))
    for directory in ('backend', 'scripts', 'tests'):
        for path in (ROOT / directory).rglob('*.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.ImportFrom) and not node.level:
                    assert node.module not in modules, str(path)
                if isinstance(node, ast.Import):
                    assert not modules.intersection(a.name for a in node.names), str(path)

def test_backend_resources_resolve_to_project_root(monkeypatch):
    from backend.api import api
    from backend.auth.auth import AuthManager
    monkeypatch.delenv('REPOLENS_AUTH_DIR', raising=False)
    assert api.FRONTEND_DIST == ROOT / 'frontend' / 'dist'
    assert (Path(api.__file__).resolve().parents[2] / 'frontend/public/join.html').is_file()
    # Check default storage without creating credentials in the source tree.
    assert Path(__import__('backend.auth.auth', fromlist=['x']).__file__).resolve().parents[2] == ROOT
