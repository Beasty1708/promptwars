"""
Context Events and Explainability API Router
"""
from fastapi import APIRouter, Query
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from ..db import get_db_connection
from ..services.context_engine import ContextEngine

router = APIRouter(prefix="/api/context", tags=["Context"])
context_engine = ContextEngine()

@router.get("/events")
def list_events():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM context_events ORDER BY start_at ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.get("/explain")
def explain_location(
    latitude: float = Query(...),
    longitude: float = Query(...),
    timestamp: Optional[str] = Query(None)
):
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    return context_engine.evaluate_context(latitude, longitude, ts)
