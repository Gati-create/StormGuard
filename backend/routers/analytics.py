"""Analytics chart series."""
from fastapi import APIRouter, Request

from backend.engines import analytics_engine
from backend.routers import deps

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary")
def analytics_summary(request: Request):
    conn = deps.get_conn(request)
    charts = analytics_engine.all_charts(conn)
    charts["risk_factors_avg"] = analytics_engine.risk_factors_avg(conn)
    charts["trigger_counts"] = analytics_engine.trigger_counts(conn)
    charts["data_source"] = "SIMULATED (fictional demo data)"
    return charts
