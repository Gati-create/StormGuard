"""Test fixtures: a temp DB seeded with a SMALL fleet (600 riders — the exact
prefix of the canonical 12,482) and a FastAPI TestClient. Every test starts
from the deterministic baseline via POST /api/simulation/reset."""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

_TMP = tempfile.mkdtemp(prefix="rideshield_test_")
os.environ["RIDESHIELD_DB"] = os.path.join(_TMP, "test.db")

import pytest  # noqa: E402

from backend import database  # noqa: E402
from backend.seed import seed  # noqa: E402

TEST_FLEET = 600


@pytest.fixture(scope="session")
def db_conn():
    conn = database.init_db()
    seed(conn, limit=TEST_FLEET)
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def client(db_conn):
    from fastapi.testclient import TestClient

    from backend.main import app
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def reset_baseline(client):
    client.post("/api/simulation/reset")
    yield
