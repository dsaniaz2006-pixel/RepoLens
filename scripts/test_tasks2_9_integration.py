"""Offline frontend/public artifact integration checks for Tasks 2–9.
No external AI, OAuth or database services are impersonated by these checks.
"""
from __future__ import annotations
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
FRONT = ROOT / 'frontend'

class GalleryParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag == 'a':
            href=dict(attrs).get('href','')
            if re.fullmatch(r'/gallery/[a-z0-9-]+/index\.html',href):
                self.links.append(href)

class UIIntegration(unittest.TestCase):
    def test_catalog_links_resolve_to_real_reports(self):
        parser=GalleryParser()
        parser.feed((FRONT/'gallery/index.html').read_text())
        self.assertEqual(20,len(parser.links))
        for href in parser.links:
            report=FRONT/'public'/href.lstrip('/')
            self.assertTrue(report.is_file(),str(report))
            html=report.read_text()
            self.assertIn('Source snapshot',html)

    def test_public_sites_use_published_reveal_assets(self):
        self.assertTrue((FRONT/'public/site/reveal.js').is_file())
        self.assertTrue((FRONT/'public/reveal.css').is_file())
        for name in ('index.html','gallery/index.html','docs/index.html','login/index.html','signup/index.html','blog/index.html','pricing/index.html','examples/index.html','demo/index.html'):
            html=(FRONT/name).read_text()
            self.assertIn('/site/reveal.js',html,name)
            self.assertIn('/reveal.css',html,name)

    def test_original_oauth_entry_pages_remain(self):
        for name in ('login','signup'):
            html=(FRONT/name/'index.html').read_text()
            self.assertIn('auth-root',html)
            self.assertIn('src/auth.jsx',html)
        self.assertIn('/api/auth/me',(FRONT/'src/main.jsx').read_text())

    def test_https_path_is_preserved(self):
        launcher=(ROOT/'start.mjs').read_text()
        self.assertTrue('https' in launcher.lower())
        self.assertTrue((ROOT/'scripts/setup_local_https.mjs').exists())
        self.assertTrue((ROOT/'scripts/verify_local_https.mjs').exists())

    def test_native_scrolling_and_one_view_rule(self):
        """Wheel gestures no longer switch workspace views; click navigation remains."""
        main=(FRONT/'src/main.jsx').read_text()
        self.assertNotIn('useWorkspaceWheelNavigation',main)
        self.assertNotIn('WORKSPACE_SCROLL_ORDER',main)
        self.assertFalse((FRONT/'src/useWorkspaceWheelNavigation.js').exists())
        self.assertFalse((FRONT/'src/workspaceWheelTiming.js').exists())
        self.assertIn("page==='Public Gallery'?<GalleryWorkspace",main)
        self.assertIn("page==='Home'?<Home",main)
        self.assertIn('key={page} ref={contentRef}',main)
        self.assertIn('onClick={()=>active(n)}',main)


if __name__=='__main__':unittest.main(verbosity=2)
