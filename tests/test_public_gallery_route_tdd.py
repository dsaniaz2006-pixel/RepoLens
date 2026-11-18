"""Regression: gallery HTML exists over FastAPI before and after the Vite build.

The original optional StaticFiles mount only existed if frontend/dist was
present at API import time, so isolated Python tests got a 404 for /gallery/.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest


def test_public_gallery_served_from_source_without_build(tmp_path, monkeypatch):
    from backend.api import public_gallery
    monkeypatch.setattr(public_gallery, 'FRONTEND_ROOT', tmp_path / 'frontend')
    source = tmp_path / 'frontend' / 'gallery' / 'index.html'
    source.parent.mkdir(parents=True)
    source.write_text('<html><h1>Public RepoLens gallery</h1></html>')
    snapshot = tmp_path / 'frontend' / 'public' / 'gallery' / 'pallets-flask' / 'index.html'
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text('<html>Cached example report</html>')
    app = FastAPI()
    app.include_router(public_gallery.router)
    client = TestClient(app)
    assert client.get('/gallery/').status_code == 200
    assert 'Public RepoLens gallery' in client.get('/gallery/').text
    assert client.get('/gallery/pallets-flask/').status_code == 200
    assert 'Cached example report' in client.get('/gallery/pallets-flask/index.html').text
    assert client.get('/gallery/secret-file/').status_code == 404
    assert client.get('/gallery/.env/').status_code == 404
    assert client.get('/gallery/../').status_code == 404


def test_public_gallery_prefers_compiled_dist_after_build(tmp_path, monkeypatch):
    from backend.api import public_gallery
    monkeypatch.setattr(public_gallery, 'FRONTEND_ROOT', tmp_path / 'frontend')
    source = tmp_path / 'frontend' / 'gallery' / 'index.html'
    source.parent.mkdir(parents=True)
    source.write_text('<html>Unbuilt source</html>')
    built = tmp_path / 'frontend' / 'dist' / 'gallery' / 'index.html'
    built.parent.mkdir(parents=True)
    built.write_text('<html>Built gallery</html>')
    app = FastAPI()
    app.include_router(public_gallery.router)
    response = TestClient(app).get('/gallery/')
    assert response.status_code == 200
    assert response.text == '<html>Built gallery</html>'


def test_public_gallery_never_exposes_arbitrary_files(tmp_path, monkeypatch):
    from backend.api import public_gallery
    monkeypatch.setattr(public_gallery, 'FRONTEND_ROOT', tmp_path / 'frontend')
    (tmp_path / 'frontend' / 'public' / 'gallery').mkdir(parents=True)
    (tmp_path / 'frontend' / 'public' / '.env').write_text('SECRET=do-not-serve')
    app = FastAPI()
    app.include_router(public_gallery.router)
    client = TestClient(app)
    for uri in ['/gallery/hidden/','/gallery/%2E%2E/','/gallery/hidden/index.html']:
        response = client.get(uri)
        assert response.status_code in (404, 307)
        assert 'do-not-serve' not in response.text


def test_real_repository_gallery_exists_before_vite_build():
    """FastAPI's anonymous gallery contract does not depend on frontend/dist."""
    from backend.api.public_gallery import router
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    landing = client.get('/gallery/')
    assert landing.status_code == 200
    assert '20 repositories' in landing.text
    snapshot = client.get('/gallery/pallets-flask/')
    assert snapshot.status_code == 200
    assert 'Source snapshot — AI review pending' in snapshot.text
    styles = client.get('/gallery/gallery.css')
    assert styles.status_code == 200
    assert 'text/css' in styles.headers['content-type']
