"""Phase 10 end-to-end publication pipeline without external provider credentials."""
from pathlib import Path
import json
import functools
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from threading import Thread
from urllib.request import urlopen


def test_phase10_generated_reviewed_published_and_served_anonymously(tmp_path, monkeypatch):
    from scripts import prebuild_gallery as pagebuilder
    from backend.services import gallery_pipeline as gallery
    from tests.test_analyzer import TREE, valid_analysis
    from backend.services.report import render_report

    monkeypatch.setattr(pagebuilder, 'ROOT', tmp_path)
    monkeypatch.setenv('REPOLENS_MODEL_PROVIDER','gemini')
    def mock_report(url, output_dir, **kwargs):
        folder=Path(output_dir);folder.mkdir(parents=True,exist_ok=True)
        metadata={'full_name':'pallets/flask','html_url':url}
        analysis=valid_analysis();path=folder/'generated.md'
        path.write_text(render_report(analysis,metadata,TREE))
        return {'analysis':analysis,'metadata':metadata,'tree':TREE,'report_path':str(path),
                'revision':'a'*40,'evidence_paths':[r['path'] for r in TREE if r['type']=='blob']}
    # Generator's structural checks cannot count as a manual source review.
    item=gallery.generate_ai_reports(tmp_path,['pallets/flask'],generator=mock_report)[0]
    assert item['status']=='generated'
    assert gallery.publish(tmp_path,['pallets/flask'])==[]
    packet=gallery.review_packet(tmp_path,'pallets/flask')
    assert 'Every claimed file path exists' in packet.read_text()
    assert 'source' in packet.read_text().lower()
    gallery.approve(tmp_path,'pallets/flask','Human source reviewer')
    assert gallery.publish(tmp_path,['pallets/flask'])==['pallets/flask']
    pagebuilder.build()
    index=tmp_path/'frontend/gallery/index.html'
    assert 'pallets/flask' in index.read_text()
    # Serve an actual static export over HTTP to test anonymous navigation.
    site=tmp_path/'site'
    (site/'gallery/pallets-flask').mkdir(parents=True)
    (site/'gallery/index.html').write_bytes(index.read_bytes())
    (site/'gallery/pallets-flask/index.html').write_bytes((tmp_path/'frontend/public/gallery/pallets-flask/index.html').read_bytes())
    handler=functools.partial(SimpleHTTPRequestHandler,directory=str(site))
    server=ThreadingHTTPServer(('127.0.0.1',0),handler)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        base=f'http://127.0.0.1:{server.server_address[1]}'
        with urlopen(base+'/gallery/') as response:
            assert response.status==200
            assert b'pallets/flask' in response.read()
        with urlopen(base+'/gallery/pallets-flask/index.html') as response:
            assert response.status==200
            body=response.read().decode()
            assert 'Reviewed AI architecture report' in body
            assert 'href="/dashboard/"' in body
            assert 'github.com/pallets/flask/blob/' in body
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)


def test_phase10_report_approval_does_not_auto_publish(tmp_path):
    from backend.services.gallery_pipeline import publication_receipt
    assert publication_receipt(tmp_path,'pallets/flask',{}) is False
