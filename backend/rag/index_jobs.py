"""Bounded repository indexing jobs with restart-safe, account-scoped receipts.

Only the default API singleton uses on-disk storage. Test instances remain in
memory unless an explicit storage_path is supplied. The saved records contain
job URLs/status, never tokens or repository source. A worker restart can resume
interrupted jobs using the persistent per-chunk embedding cache.
"""
import json
import os
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Event, RLock
from time import monotonic
from uuid import uuid4

from backend.core.operation_progress import _current, OperationStopped


class IndexJobs:
    def __init__(self, timeout=900, capacity=2, storage_path=None):
        self.timeout, self.capacity = timeout, capacity
        self.jobs = {}
        self.lock = RLock()
        self.pool = ThreadPoolExecutor(max_workers=capacity, thread_name_prefix='repolens-index')
        self.storage_path = Path(storage_path) if storage_path else None
        if self.storage_path:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with self._database() as connection:
                connection.execute('''CREATE TABLE IF NOT EXISTS index_jobs (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, url TEXT NOT NULL,
                    state TEXT NOT NULL, message TEXT NOT NULL, result TEXT,
                    error TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL,
                    cancel_requested INTEGER NOT NULL DEFAULT 0
                )''')
                for row in connection.execute('SELECT * FROM index_jobs WHERE updated_at > ?',
                                              (time.time() - 86400,)).fetchall():
                    state = row['state']
                    if state == 'running':
                        state = 'cancelled' if row['cancel_requested'] else 'interrupted'
                    job = dict(id=row['id'], owner=row['owner'], url=row['url'],
                               state=state, message=('Index interrupted by a server restart; resuming saved batches…'
                                                     if state == 'interrupted' else row['message']),
                               result=json.loads(row['result']) if row['result'] else None,
                               error=row['error'], created_at=row['created_at'],
                               cancel=Event(), started=monotonic())
                    self.jobs[job['id']] = job
                    if state != row['state']:
                        self._persist(connection, job)
            try:
                self.storage_path.chmod(0o600)
            except OSError:
                pass

    @contextmanager
    def _database(self):
        connection = sqlite3.connect(self.storage_path, timeout=15)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _persist(self, connection, job):
        connection.execute('''INSERT INTO index_jobs
            (id, owner, url, state, message, result, error, created_at, updated_at, cancel_requested)
            VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
            state=excluded.state, message=excluded.message, result=excluded.result,
            error=excluded.error, updated_at=excluded.updated_at,
            cancel_requested=excluded.cancel_requested''',
            (job['id'], job['owner'], job['url'], job['state'], job['message'],
             json.dumps(job['result']) if job['result'] is not None else None,
             job['error'], job['created_at'], time.time(), int(job['cancel'].is_set())))

    def _save(self, job):
        if self.storage_path:
            with self._database() as connection:
                with connection:
                    self._persist(connection, job)

    @staticmethod
    def snapshot(job):
        return {k: v for k, v in job.items() if k not in ('owner', 'cancel', 'started', 'created_at')}

    def start(self, owner, url, run, error_message):
        from backend.github.github_client import parse_github_url
        owner_name, repo_name = parse_github_url(url)
        url = f'https://github.com/{owner_name}/{repo_name}'.lower()
        with self.lock:
            now = monotonic()
            self.jobs = {k: v for k, v in self.jobs.items()
                         if v['state'] in ('running', 'interrupted') or now - v['started'] < 3600}
            active = [j for j in self.jobs.values() if j['state'] == 'running']
            for job in active:
                if job['owner'] == owner:
                    if job['url'] == url:
                        return self.snapshot(job)
                    raise ValueError('An index is already running. Cancel it before indexing another repository.')
            if any(j['url'] == url for j in active):
                raise ValueError('This repository is currently being indexed. Please retry shortly.')
            if len(active) >= self.capacity:
                raise ValueError('The index worker is busy. Please retry when another index finishes.')
            # A restart with automatic recovery disabled still supports explicit
            # resumption of the same job rather than wasting the saved progress.
            matching = next((j for j in self.jobs.values() if j['state'] == 'interrupted'
                             and j['owner'] == owner and j['url'] == url), None)
            if matching:
                job = matching
                job.update(state='running', started=now,
                           message='Resuming the saved index after server restart…', error=None)
                job['cancel'].clear()
            else:
                job = dict(id=uuid4().hex, owner=owner, url=url, state='running',
                           message='Starting repository index…', result=None, error=None,
                           cancel=Event(), started=now, created_at=time.time())
                self.jobs[job['id']] = job
            self._save(job)
        self.pool.submit(self._run, job, run, error_message)
        return self.snapshot(job)

    def recover(self, run, error_message):
        """Queue interrupted jobs after app startup, using a trusted run factory.

        The run callback accepts (owner_id, repository_url). A dedicated API
        worker should be used; concurrent app workers must not share this DB.
        """
        restarted = []
        with self.lock:
            for job in self.jobs.values():
                if job['state'] != 'interrupted':
                    continue
                job.update(state='running', started=monotonic(),
                           message='Resuming saved embedding batches after server restart…', error=None)
                self._save(job)
                restarted.append(job)
        for job in restarted:
            self.pool.submit(self._run, job,
                             lambda url, owner=job['owner']: run(owner, url), error_message)
        return len(restarted)

    def _run(self, job, run, error_message):
        def progress(message):
            if job['cancel'].is_set():
                raise OperationStopped('Index cancelled. Completed embedding batches are saved for retry.')
            if monotonic() - job['started'] > self.timeout:
                raise OperationStopped('Index reached the 15-minute limit. Retry to resume completed embedding batches; check provider quota and connectivity.')
            if message:
                with self.lock:
                    job['message'] = message
                    self._save(job)
        token = _current.set(progress)
        try:
            progress(None)
            result = run(job['url'])
            progress(None)
            with self.lock:
                job.update(state='completed', result=result, message='Index ready. You can ask repository questions.')
                self._save(job)
        except OperationStopped as exc:
            with self.lock:
                job.update(state='cancelled' if job['cancel'].is_set() else 'failed',
                           error=str(exc), message=str(exc))
                self._save(job)
        except Exception as exc:
            with self.lock:
                try:
                    safe_error = error_message(exc)
                except Exception:
                    safe_error = 'Index failed. Check the backend logs.'
                job.update(state='failed', error=safe_error,
                           message='Index failed. Fix the reported issue and retry.')
                self._save(job)
        finally:
            _current.reset(token)

    def get(self, owner, job_id, cancel=False):
        with self.lock:
            job = self.jobs.get(job_id)
            if not job or job['owner'] != owner:
                return None
            if cancel and job['state'] == 'running':
                job['cancel'].set()
                job['message'] = 'Cancellation requested; waiting for the current network request to finish…'
                self._save(job)
            elif cancel and job['state'] == 'interrupted':
                job.update(state='cancelled', message='Saved job cancelled before recovery.')
                self._save(job)
            return self.snapshot(job)


def default_jobs_path():
    root = Path(__file__).resolve().parents[2]
    folder = Path(os.getenv('REPOLENS_AUTH_DIR', str(root / '.repolens_auth')))
    return Path(os.getenv('REPOLENS_INDEX_JOBS_DB', str(folder / 'index_jobs.sqlite3')))


jobs = IndexJobs(storage_path=default_jobs_path())
