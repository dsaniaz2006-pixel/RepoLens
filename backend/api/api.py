"""Local-first FastAPI interface for RepoLens. Run via uvicorn backend.api.api:app."""
from __future__ import annotations
import json
import asyncio
import threading
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from backend.core.environment import PROJECT_ROOT, load_project_environment
from backend.api.errors import validation_error_response, raise_report_api_error

# Uvicorn imports api.py directly, bypassing main.py's .env loader.
# Anchor the file to this module so startup works from any working directory.
load_project_environment()

from backend.services.pipeline import generate_report, index_repo, ask_repo, collect_repo
from backend.ai.extra_modes import interview_mode, contribution_mode
from backend.github.github_client import parse_github_url
from backend.api.schemas import AnalyzeRequest, AskRequest

from contextlib import asynccontextmanager
@asynccontextmanager
async def lifespan(app):
    await start_freshness_worker()
    # Interrupted jobs are resumed after the API has initialized its storage.
    # Per-chunk embedding cache avoids repeating successful Gemini requests.
    if os.getenv('REPOLENS_INDEX_AUTO_RESUME', 'true').lower() in ('1', 'true', 'yes'):
        from backend.api.product_api import track_index
        from backend.database.product_store import configured_engine
        def recover_job(owner, url):
            result = index_repo(url)
            track_index(configured_engine(), owner, url, result)
            return result
        jobs.recover(recover_job, _job_error)
    try: yield
    finally: await stop_freshness_worker()

app = FastAPI(title='RepoLens API', version='1.1.0-rc.1', lifespan=lifespan)
from backend.auth.auth import install_auth
install_auth(app)

REPORT_DIR = Path(os.environ.get('REPOLENS_REPORT_DIR','reports'))

def user_report_dir(request: Request):
    return REPORT_DIR / 'users' / request.state.user['id']

@app.exception_handler(RequestValidationError)
async def safe_validation_response(request, exc):
    return await validation_error_response(request, exc)


def _error(exc):
    # Keep the existing call contract used by reports, RAG and background jobs.
    raise_report_api_error(exc)

from backend.api.product_api import router as product_router
app.include_router(product_router)
# Public, read-only Gallery HTML remains available even when FastAPI is
# imported before Vite builds frontend/dist (e.g. isolated API tests).
from backend.api.public_gallery import router as public_gallery_router
app.include_router(public_gallery_router)

async def start_freshness_worker():
    import asyncio
    from types import SimpleNamespace
    from backend.database.product_store import engine
    from backend.services.freshness import run_due
    if os.getenv("REPOLENS_FRESHNESS_SCHEDULER","internal")!="internal":
        app.state.freshness_worker=None
        return
    db=engine(SimpleNamespace(app=app))
    async def worker():
        while True:
            try: await run_in_threadpool(run_due,db)
            except Exception: pass  # Individual records expose check failures; retry next cycle.
            await asyncio.sleep(300)
    app.state.freshness_worker=asyncio.create_task(worker())

async def stop_freshness_worker():
    import asyncio
    task=getattr(app.state,'freshness_worker',None)
    if task:
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass

@app.get('/api/health')
def health():
    return {'status':'ok'}

@app.get('/api/usage')
def usage(request: Request):
    """Authenticated UTC-day quotas. Never returns any shared IP data."""
    try:
        return request.app.state.auth.usage_snapshot(request.state.user['id'])
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error('Usage read unavailable (%s)', type(exc).__name__)
        raise HTTPException(503, 'Usage data is temporarily unavailable. Check database migrations.') from None

@app.get('/api/config-status')
def config_status():
    """Safe diagnostic: only presence flags, never credential values."""
    dotenv_file = PROJECT_ROOT / '.env'
    # Re-read so adding a .env file after server startup can be diagnosed.
    load_project_environment()
    return {
        'env_file_exists': dotenv_file.is_file(),
        'model_provider': os.getenv('REPOLENS_MODEL_PROVIDER','gemini'),
        'gemini_key_configured': bool(os.environ.get('GEMINI_API_KEY', '').strip()),
        'github_token_configured': bool(os.environ.get('GITHUB_TOKEN', '').strip()),
        'message': 'If a key is missing, put .env in the project root (alongside requirements.txt) and restart FastAPI.'
    }

@app.post('/api/analyze')
async def analyze(body: AnalyzeRequest, request: Request):
    report_dir = user_report_dir(request)
    try:
        result = await run_in_threadpool(generate_report,body.url,output_dir=str(report_dir),overwrite=True)
        _save_analysis_history(report_dir, body.url, result)
        return result
    except Exception as exc:
        _error(exc)

def _save_analysis_history(report_dir: Path, url: str, result: dict) -> None:
    """Store only report metadata; never persist downloaded source or provider keys."""
    owner, repo = parse_github_url(url)
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / f'{owner}-{repo}-analysis.json').write_text(json.dumps({
        'analysis': result['analysis'], 'metadata': result['metadata'],
        'tree': result['tree'], 'truncated': result['truncated'],
        'revision': result.get('revision'), 'evidence_paths': result.get('evidence_paths')
    }, ensure_ascii=False), encoding='utf-8')


def _stream_data(event: dict) -> str:
    """Serialize one complete SSE message without embedding sensitive errors."""
    return 'data: ' + json.dumps(event, ensure_ascii=False) + '\n\n'


@app.post('/api/analyze/stream')
async def analyze_stream(body: AnalyzeRequest, request: Request):
    """Push stage progress while keeping legacy /api/analyze unchanged.

    One authenticated request uses one normal analysis quota reservation.
    Provider operations run in a worker thread; a disconnected client stops
    at the next cooperative progress boundary, not mid-HTTP provider call.
    """
    report_dir = user_report_dir(request)

    async def events():
        loop = asyncio.get_running_loop()
        messages: asyncio.Queue = asyncio.Queue(maxsize=64)
        disconnected = threading.Event()
        finished = threading.Event()

        def send(event):
            if disconnected.is_set():
                return
            def put():
                if not disconnected.is_set():
                    # Stage updates are bounded and low frequency; avoid
                    # leaking thread exceptions into the response stream.
                    try: messages.put_nowait(event)
                    except asyncio.QueueFull: pass
            loop.call_soon_threadsafe(put)

        def progress(message):
            from backend.core.operation_progress import OperationStopped
            if disconnected.is_set():
                raise OperationStopped('Analysis connection closed')
            if message:
                send({'status': 'progress', 'message': str(message)[:180]})

        def worker():
            from backend.core.operation_progress import _current, OperationStopped
            token = _current.set(progress)
            try:
                progress('Starting repository analysis…')
                result = generate_report(body.url, output_dir=str(report_dir), overwrite=True)
                progress('Saving report to your history…')
                _save_analysis_history(report_dir, body.url, result)
                send({'status': 'done', 'result': result})
            except OperationStopped:
                pass
            except Exception as exc:
                try:
                    _error(exc)
                except HTTPException as err:
                    send({'status': 'error', 'message': str(err.detail)[:180]})
                else:
                    send({'status': 'error', 'message': 'Repository analysis failed.'})
            finally:
                _current.reset(token)
                finished.set()
                send({'status': 'finished'})

        job = asyncio.create_task(asyncio.to_thread(worker))
        try:
            yield _stream_data({'status': 'progress', 'message': 'Connecting to analysis worker…'})
            while True:
                try:
                    event = await asyncio.wait_for(messages.get(), timeout=8)
                except asyncio.TimeoutError:
                    if finished.is_set():
                        break
                    # Keep proxy buffers from hiding a stalled provider request.
                    yield ': heartbeat\n\n'
                    continue
                if event.get('status') == 'finished':
                    break
                yield _stream_data(event)
                if event.get('status') in ('done', 'error'):
                    break
        finally:
            disconnected.set()
            # Observe errors rather than allowing unhandled task warnings.
            if job.done():
                try: job.result()
                except Exception: pass

    return StreamingResponse(events(), media_type='text/event-stream', headers={
        'Cache-Control': 'no-cache, no-transform',
        'X-Accel-Buffering': 'no', 'X-Content-Type-Options': 'nosniff',
    })


def _optional_mode(url: str, mode: str):
    """Reuse the approved, bounded repository evidence for optional features."""
    data = collect_repo(url)
    if mode == 'interview':
        return interview_mode(data['metadata'], data['records'])
    return contribution_mode(data['metadata'], data['records'])


@app.post('/api/interview')
async def interview(body: AnalyzeRequest):
    try:
        return await run_in_threadpool(_optional_mode, body.url, 'interview')
    except Exception as exc:
        _error(exc)


@app.post('/api/contribution')
async def contribution(body: AnalyzeRequest):
    try:
        return await run_in_threadpool(_optional_mode, body.url, 'contribution')
    except Exception as exc:
        _error(exc)


from backend.rag.index_jobs import jobs

def _job_error(exc):
    try:
        _error(exc)
    except HTTPException as error:
        return error.detail

@app.post('/api/index/jobs', status_code=202)
def start_index_job(body: AnalyzeRequest, request: Request):
    try:
        parse_github_url(body.url)
        from backend.ai.model_provider import provider
        if provider()!='ollama' and not os.environ.get('GEMINI_API_KEY', '').strip():
            raise ValueError('GEMINI_API_KEY is missing; add your Google AI Studio key to .env in the project root (alongside requirements.txt) and restart the server. Google sign-in credentials do not enable Gemini.')
        from backend.api.product_api import track_index
        from backend.database.product_store import engine
        db=engine(request);user=request.state.user['id']
        def index_and_track(url, **kwargs):
            result=index_repo(url,**kwargs)
            track_index(db,user,url,result)
            return result
        return jobs.start(user, body.url.strip().rstrip('/'), index_and_track, _job_error)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

@app.get('/api/jobs/{job_id}')
def index_job_status(job_id: str, request: Request):
    result = jobs.get(request.state.user['id'], job_id)
    if result is None:
        raise HTTPException(404, 'Index job not found. The server may have restarted; start the index again to resume saved batches.')
    return result

@app.post('/api/jobs/{job_id}/cancel')
def cancel_index_job(job_id: str, request: Request):
    result = jobs.get(request.state.user['id'], job_id, cancel=True)
    if result is None: raise HTTPException(404, 'Index job not found')
    return result

@app.post('/api/index')
async def index(body: AnalyzeRequest, request: Request):
    try:
        result=await run_in_threadpool(index_repo,body.url)
        from backend.api.product_api import track_index
        from backend.database.product_store import engine
        await run_in_threadpool(track_index,engine(request),request.state.user['id'],body.url,result)
        return result
    except Exception as exc: _error(exc)

@app.post('/api/ask')
async def ask(body: AskRequest, request: Request):
    try:
        if body.conversation_id:
            from backend.database.conversations import request_store
            return await run_in_threadpool(ask_repo,body.url,body.question,conversation_id=body.conversation_id,
                user_id=request.state.user['id'],store=request_store(request),version=body.version)
        return await run_in_threadpool(ask_repo,body.url,body.question)
    except Exception as exc: _error(exc)

@app.get('/api/conversations')
def list_conversations(request: Request):
    from backend.database.conversations import request_store
    return request_store(request).listing(request.state.user['id'])

@app.post('/api/conversations')
def create_conversation(body: AnalyzeRequest, request: Request):
    from backend.database.conversations import request_store
    from backend.services.pipeline import fetch_repo_metadata, fetch_commit_sha, resume_completed_index
    try:
        owner,repo=parse_github_url(body.url)
        metadata=fetch_repo_metadata(owner,repo)
        if metadata.get('private'): raise ValueError('Only public repositories are supported')
        revision=fetch_commit_sha(owner,repo,metadata['default_branch'])
        name=f'{owner}/{repo}'.lower()
        if not resume_completed_index(name,revision): raise ValueError('Build / Refresh the RAG index for the current revision before starting a chat.')
        return request_store(request).create(request.state.user['id'],name,revision)
    except Exception as exc: _error(exc)

@app.get('/api/conversations/{conversation_id}/messages')
def conversation_messages(conversation_id: str, request: Request):
    from backend.database.conversations import request_store
    return request_store(request).get(request.state.user['id'],conversation_id)

@app.delete('/api/conversations/{conversation_id}')
def delete_conversation(conversation_id: str, request: Request):
    from backend.database.conversations import request_store
    request_store(request).remove(request.state.user['id'],conversation_id)
    return {'deleted':True}

@app.get('/api/history')
def history(request: Request):
    report_dir = user_report_dir(request)
    if not report_dir.exists(): return []
    results=[]
    for path in sorted(report_dir.glob('*-analysis.json'),key=lambda x:x.stat().st_mtime,reverse=True)[:30]:
        try:
            data=json.loads(path.read_text(encoding='utf-8'))
            results.append({'metadata':data['metadata'],'filename':path.name,'modified':path.stat().st_mtime})
        except (OSError,ValueError,KeyError): continue
    return results

@app.get('/api/history/{owner}/{repo}')
def historical_report(owner:str,repo:str,request: Request):
    report_dir = user_report_dir(request)
    try: parse_github_url(f'https://github.com/{owner}/{repo}')
    except ValueError: raise HTTPException(400,'Invalid repository name')
    p=report_dir/f'{owner}-{repo}-analysis.json'
    if not p.exists(): raise HTTPException(404,'Analysis not found')
    try: return json.loads(p.read_text(encoding='utf-8'))
    except (OSError,ValueError): raise HTTPException(500,'Saved analysis is corrupted')

@app.get('/api/report/{owner}/{repo}')
def download_report(owner:str,repo:str,request: Request):
    report_dir = user_report_dir(request)
    try: parse_github_url(f'https://github.com/{owner}/{repo}')
    except ValueError: raise HTTPException(400,'Invalid repository name')
    path=report_dir/f'{owner}-{repo}-report.md'
    if not path.is_file(): raise HTTPException(404,'Report not found')
    return FileResponse(path,media_type='text/markdown',filename=path.name)

@app.get('/api/report/{owner}/{repo}/pdf')
def download_pdf(owner:str,repo:str,request: Request):
    report_dir = user_report_dir(request)
    try: parse_github_url(f'https://github.com/{owner}/{repo}')
    except ValueError: raise HTTPException(400,'Invalid repository name')
    path=report_dir/f'{owner}-{repo}-report.md'
    if not path.is_file(): raise HTTPException(404,'Report not found')
    try:
        from io import BytesIO
        from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.pagesizes import A4
        from xml.sax.saxutils import escape
        from fastapi.responses import Response
        buffer=BytesIO();doc=SimpleDocTemplate(buffer,pagesize=A4)
        styles=getSampleStyleSheet();story=[]
        for raw in path.read_text(encoding='utf-8').splitlines():
            line=raw.strip()
            if not line: story.append(Spacer(1,9));continue
            level=len(line)-len(line.lstrip('#'))
            style=styles['Heading1' if level==1 else 'Heading2' if level==2 else 'Heading3' if level==3 else 'BodyText']
            safe=escape(line[level:].strip() if 1<=level<=3 else line)
            story.append(Paragraph(safe,style))
        doc.build(story)
        return Response(content=buffer.getvalue(),media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="{owner}-{repo}-report.pdf"'})
    except Exception as exc:
        _error(exc)

@app.get('/join')
def join_page():
    return FileResponse(Path(__file__).resolve().parents[2]/'frontend/public/join.html',headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer'})

# Serve only the built frontend, never the repository or private account storage.
# API/auth routes are registered before this fallback. The auth middleware guards
# /dashboard and every dashboard HTML path before StaticFiles can serve them.
from fastapi.staticfiles import StaticFiles
FRONTEND_DIST = Path(__file__).resolve().parents[2] / 'frontend' / 'dist'
if FRONTEND_DIST.is_dir():
    app.mount('/', StaticFiles(directory=str(FRONTEND_DIST), html=True), name='website')
