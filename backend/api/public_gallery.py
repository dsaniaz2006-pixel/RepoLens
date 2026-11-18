"""Allowlisted, anonymous public gallery routes.

Vite serves these pages in local development. When FastAPI is tested directly,
frontend/dist might not exist *yet*, so the optional static mount in api.py
cannot serve any page. These explicit routes keep the gallery contract stable
without exposing the source tree, private reports, or authentication data.

When a compiled page is present it always wins over the source copy.
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

FRONTEND_ROOT = Path(__file__).resolve().parents[2] / 'frontend'
router = APIRouter(include_in_schema=False)


def _public_file(*, built: Path, source: Path) -> FileResponse:
    for candidate in (built, source):
        if candidate.is_file():
            return FileResponse(candidate)
    raise HTTPException(status_code=404, detail='Public gallery page not found')


@router.get('/gallery/')
def gallery_landing():
    return _public_file(
        built=FRONTEND_ROOT / 'dist' / 'gallery' / 'index.html',
        source=FRONTEND_ROOT / 'gallery' / 'index.html',
    )


@router.get('/gallery/gallery.css')
def gallery_styles():
    return _public_file(
        built=FRONTEND_ROOT / 'dist' / 'gallery' / 'gallery.css',
        source=FRONTEND_ROOT / 'public' / 'gallery' / 'gallery.css',
    )


@router.get('/gallery/{slug}/')
@router.get('/gallery/{slug}/index.html')
def gallery_snapshot(slug: str):
    # No arbitrary paths, dots, nested directories or private account reports.
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug, flags=re.ASCII):
        raise HTTPException(status_code=404, detail='Public gallery page not found')
    return _public_file(
        built=FRONTEND_ROOT / 'dist' / 'gallery' / slug / 'index.html',
        source=FRONTEND_ROOT / 'public' / 'gallery' / slug / 'index.html',
    )
