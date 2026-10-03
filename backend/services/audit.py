"""Append-only audit trail writer. Every row is AU-<seq> with an event_code
from the contract list."""
import json
from datetime import datetime

from backend.services import ids


def audit(conn, event_code, entity_type, entity_id, detail, created_at=None):
    seq = ids.next_seq(conn, "audit_events")
    audit_id = ids.fmt("AU", seq)
    conn.execute(
        "INSERT INTO audit_events (audit_id, event_code, entity_type, entity_id, detail, created_at)"
        " VALUES (?,?,?,?,?,?)",
        (
            audit_id,
            event_code,
            entity_type,
            str(entity_id),
            json.dumps(detail),
            created_at or datetime.utcnow().isoformat(timespec="seconds") + "Z",
        ),
    )
    return audit_id
