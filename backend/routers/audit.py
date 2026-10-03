"""Audit trail endpoint."""
from fastapi import APIRouter, Request

from backend.routers import deps

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit(request: Request, limit: int = 200):
    conn = deps.get_conn(request)
    limit = max(1, min(limit, 1000))
    rows = conn.execute(
        "SELECT audit_id, event_code, entity_type, entity_id, detail, created_at"
        " FROM audit_events ORDER BY created_at DESC, audit_id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return {"entries": [dict(r) for r in rows]}
