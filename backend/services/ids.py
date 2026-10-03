"""Human-readable ID sequencing helpers (W-…, EV-…, CL-…, AU-… conventions)."""
from typing import Optional


def next_seq(conn, table):
    # Sequences are 1-based counts; callers doing batch inserts take the base
    # once and increment locally inside the same transaction.
    row = conn.execute("SELECT COUNT(*) AS c FROM %s" % table).fetchone()
    return int(row["c"]) + 1


def fmt(prefix, seq):
    return "%s-%06d" % (prefix, seq)


def next_event_id(conn, date_str, created_at=None):
    # EV-<yyyymmdd>-<seq>, seq counts events already stored for that date.
    like = "EV-%s-%%" % date_str
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM weather_events WHERE event_id LIKE ?", (like,)
    ).fetchone()
    return "EV-%s-%03d" % (date_str, int(row["c"]) + 1)
