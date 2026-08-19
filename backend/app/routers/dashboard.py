"""
Consolidated User and Guardian Dashboard API Router
"""
from fastapi import APIRouter
from typing import Dict, Any
from ..db import get_db_connection
from ..services.journey_service import JourneyService

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])
journey_service = JourneyService()

@router.get("/overview")
def get_dashboard_overview():
    conn = get_db_connection()
    cursor = conn.cursor()

    # User info
    cursor.execute("SELECT id, name, phone_masked, monitoring_enabled FROM users WHERE id = 1")
    user = cursor.fetchone()

    # Active journey
    cursor.execute("SELECT id FROM journeys WHERE user_id = 1 ORDER BY id DESC LIMIT 1")
    last_j = cursor.fetchone()
    active_journey = journey_service.get_journey(last_j["id"]) if last_j else None

    # Guardians
    cursor.execute("SELECT id, name, relationship, contact_masked, priority, enabled FROM guardians WHERE user_id = 1 ORDER BY priority ASC")
    guardians = [dict(g) for g in cursor.fetchall()]

    # Active alert count
    cursor.execute("SELECT COUNT(*) FROM alerts WHERE status = 'ACTIVE'")
    active_alerts_count = cursor.fetchone()[0]

    # Context events count
    cursor.execute("SELECT COUNT(*) FROM context_events")
    events_count = cursor.fetchone()[0]

    # Environmental risk points count
    cursor.execute("SELECT COUNT(*) FROM environmental_risk_points")
    env_points_count = cursor.fetchone()[0]

    conn.close()

    return {
        "user": dict(user) if user else {"name": "Alex Rivera", "monitoring_enabled": 1},
        "active_journey": active_journey,
        "guardians": guardians,
        "active_alerts_count": active_alerts_count,
        "events_count": events_count,
        "environmental_points_count": env_points_count
    }
