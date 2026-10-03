"""Shared router dependencies: the single DB connection, a write lock, and
small lookup helpers."""
from contextlib import contextmanager

from fastapi import HTTPException, Request


def get_conn(request: Request):
    return request.app.state.conn


@contextmanager
def write_locked(request: Request):
    with request.app.state.lock:
        try:
            yield request.app.state.conn
        except Exception:
            request.app.state.conn.rollback()
            raise


def commit(request: Request):
    request.app.state.conn.commit()


def zone_or_404(zone_id):
    from backend.engines import pricing_engine
    zone = pricing_engine.zone_by_id(zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Unknown zone %s" % zone_id)
    return zone


def worker_or_404(conn, worker_id):
    row = conn.execute("SELECT * FROM workers WHERE worker_id = ?", (worker_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown worker %s" % worker_id)
    return dict(row)
