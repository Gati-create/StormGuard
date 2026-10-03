"""Idempotency: duplicate payout attempts are no-ops at both the engine and
the database level."""
import sqlite3

import pytest

from backend import database
from backend.engines import payout_engine


def _rejected_claim(conn):
    # A reviewed-and-rejected seeded claim has no payout row yet; its worker,
    # event and policy FKs are all valid.
    row = conn.execute(
        "SELECT claim_id, worker_id, event_id, idempotency_key FROM claims"
        " WHERE status = 'REJECTED' AND claim_id NOT IN (SELECT claim_id FROM payouts)"
        " LIMIT 1").fetchone()
    assert row is not None, "expected a seeded rejected claim to attach test payouts to"
    return dict(row)


def _cleanup(conn, claim):
    conn.rollback()
    conn.execute("DELETE FROM payouts WHERE idempotency_key = ?",
                 (claim["idempotency_key"],))
    conn.commit()
    conn.close()


def test_engine_duplicate_payout_is_noop(db_conn):
    claim = _rejected_claim(db_conn)
    conn = database.connect()
    try:
        first = payout_engine.persist_payout(conn, "PO-TEST-000001", claim, 496.0)
        second = payout_engine.persist_payout(conn, "PO-TEST-000002", claim, 496.0)
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM payouts WHERE idempotency_key = ?",
            (claim["idempotency_key"],)).fetchone()["c"]
        assert count == 1
        assert first["payout_id"] == second["payout_id"] == "PO-TEST-000001"
    finally:
        _cleanup(conn, claim)


def test_raw_duplicate_insert_raises(db_conn):
    claim = _rejected_claim(db_conn)
    conn = database.connect()
    try:
        payout_engine.persist_payout(conn, "PO-TEST-000010", claim, 100.0)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO payouts (payout_id, claim_id, worker_id, event_id, amount,"
                " idempotency_key) VALUES ('PO-TEST-000011', ?, ?, ?, 100.0, ?)",
                (claim["claim_id"], claim["worker_id"], claim["event_id"],
                 claim["idempotency_key"]),
            )
    finally:
        _cleanup(conn, claim)


def test_simulate_twice_no_double_payment(client):
    r1 = client.post("/api/simulate", json={"scenario_key": "EXTREME_FLOOD"})
    assert r1.status_code == 200
    e1 = r1.json()["event_id"]
    r2 = client.post("/api/simulate", json={"scenario_key": "EXTREME_FLOOD"})
    e2 = r2.json()["event_id"]
    assert e1 != e2  # a re-run is a NEW event...

    # ...but each worker is paid at most once per event: idempotency keys unique.
    conn = database.connect()
    try:
        dupes = conn.execute(
            "SELECT idempotency_key, COUNT(*) AS c FROM payouts GROUP BY idempotency_key"
            " HAVING c > 1").fetchall()
        assert dupes == []
        # Same number of approved payouts in each identical run (held count is
        # rate-derived and identical; which riders are held is event-seeded).
        n1 = conn.execute("SELECT COUNT(*) AS c FROM payouts WHERE event_id=?",
                          (e1,)).fetchone()["c"]
        n2 = conn.execute("SELECT COUNT(*) AS c FROM payouts WHERE event_id=?",
                          (e2,)).fetchone()["c"]
        assert n1 == n2
    finally:
        conn.close()

    # Full determinism: reset + rerun reproduces exactly the same event & totals.
    client.post("/api/simulation/reset")
    r3 = client.post("/api/simulate", json={"scenario_key": "EXTREME_FLOOD"})
    t3 = r3.json()["totals"]
    client.post("/api/simulation/reset")
    r4 = client.post("/api/simulate", json={"scenario_key": "EXTREME_FLOOD"})
    assert r4.json()["event_id"] == r3.json()["event_id"]
    assert r4.json()["totals"] == t3
