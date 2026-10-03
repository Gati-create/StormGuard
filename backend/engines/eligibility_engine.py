"""Worker eligibility for an event.

Affected zones  = zones with >= 1 fired trigger.
Affected riders = active workers whose home zone is affected.
Eligible        = affected riders holding an ACTIVE policy for the current week.
"""
from backend import config


def affected_zone_ids(conn, event_id):
    rows = conn.execute(
        "SELECT DISTINCT zone_id FROM triggers WHERE event_id = ? AND fired = 1",
        (event_id,),
    ).fetchall()
    return [r["zone_id"] for r in rows]


def fetch_affected_workers(conn, zone_ids):
    if not zone_ids:
        return []
    marks = ",".join("?" for _ in zone_ids)
    rows = conn.execute(
        "SELECT * FROM workers WHERE active = 1 AND home_zone_id IN (%s) ORDER BY worker_id" % marks,
        zone_ids,
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_policies(conn, worker_ids, week_start):
    if not worker_ids:
        return {}
    marks = ",".join("?" for _ in worker_ids)
    rows = conn.execute(
        "SELECT * FROM policies WHERE week_start = ? AND worker_id IN (%s)" % marks,
        [week_start] + list(worker_ids),
    ).fetchall()
    return {r["worker_id"]: dict(r) for r in rows}


def partition(workers, policies):
    """Split affected workers into (eligible, ineligible-with-reason)."""
    eligible = []
    ineligible = []
    for w in workers:
        pol = policies.get(w["worker_id"])
        if pol is None:
            ineligible.append((w, None, "NO_ACTIVE_POLICY"))
        elif pol["status"] != "ACTIVE":
            ineligible.append((w, pol, "POLICY_%s" % pol["status"]))
        else:
            eligible.append((w, pol))
    return eligible, ineligible
