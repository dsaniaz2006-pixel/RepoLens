"""Cooperative progress/cancellation; no global request-specific state."""
from contextvars import ContextVar
import time

_current = ContextVar('repolens_operation', default=None)

class OperationStopped(Exception):
    pass

def report_progress(message):
    callback = _current.get()
    if callback:
        callback(message)

def pause(seconds):
    if _current.get() is None:
        time.sleep(seconds)
        return
    # Check cancellation during provider backoff instead of sleeping a minute.
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        report_progress(None)
        time.sleep(min(0.25, max(0, end - time.monotonic())))
