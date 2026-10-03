"""RideShield FastAPI app.

Serves JSON under /api/* and the static frontend at /. On startup the DB is
initialised and seeded (only when the workers table is empty).
"""
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend import database
from backend.routers import (analytics, audit, claims, export, fleet, insurer,
                             judge, meta, overview, pricing, protection,
                             riders, simulation, viability)
from backend.seed import seed

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")


@asynccontextmanager
async def lifespan(app):
    conn = database.init_db()
    count = conn.execute("SELECT COUNT(*) AS c FROM workers").fetchone()["c"]
    if count == 0:
        seed(conn)
    app.state.conn = conn
    app.state.lock = threading.RLock()
    app.state.last_event_id = None
    app.state.last_simulation = None
    yield
    conn.close()


app = FastAPI(title="RideShield API", version="demo-1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (meta, overview, fleet, riders, insurer, simulation, pricing,
               claims, viability, analytics, protection, audit, export, judge):
    app.include_router(module.router, prefix="/api")

if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
