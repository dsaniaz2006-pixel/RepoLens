"""Local static-server integration checks: no Google/Gemini/Neon credentials needed."""
from __future__ import annotations
import http.server
import threading
import urllib.request
from pathlib import Path
from functools import partial
import pytest

ROOT = Path(__file__).resolve().parents[1] / 'frontend'
PAGES = ('docs', 'demo', 'examples', 'pricing', 'blog')

class PublicHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(ROOT),**kwargs)
    def translate_path(self,path):
        from urllib.parse import unquote, urlsplit
        path=unquote(urlsplit(path).path)
        if path in ('/styles.css','/product.css','/favicon.svg') or path.startswith(('/reports/','/gallery/')):
            return str(ROOT / 'public' / path.lstrip('/'))
        return super().translate_path(path)
    def log_message(self,*args):
        return

@pytest.fixture(scope='module')
def static_site():
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),PublicHandler)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try: yield f'http://127.0.0.1:{server.server_port}'
    finally: server.shutdown();thread.join(timeout=3);server.server_close()

@pytest.mark.parametrize('route', PAGES)
def test_public_routes_load_without_authentication(static_site,route):
    with urllib.request.urlopen(f'{static_site}/{route}/',timeout=4) as response:
        assert response.status == 200
        assert 'text/html' in response.headers['Content-Type']
        body=response.read().decode()
    assert '<main' in body and '<h1>' in body

@pytest.mark.parametrize('route', ('styles.css','product.css','favicon.svg','reports/pallets-flask-report.md','gallery/pallets-flask/index.html'))
def test_public_assets_and_samples_load(static_site,route):
    with urllib.request.urlopen(f'{static_site}/{route}',timeout=4) as response:
        assert response.status==200
        assert len(response.read())>40

def test_demo_links_to_real_bundled_public_sample():
    assert (ROOT/'public/reports/pallets-flask-report.md').is_file()
    assert (ROOT/'public/gallery/pallets-flask/index.html').is_file()
