"""
Guardian Alerts and Escalation Inbox API Router
"""
from fastapi import APIRouter, HTTPException
import json
from typing import List, Dict, Any
from ..db import get_db_connection
from ..schemas import AlertAction
from ..services.escalation_service import EscalationService

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])

@router.get("")
def list_alerts():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, a.journey_id, a.alert_type, a.severity, a.message, a.evidence_json,
               a.created_at, a.acknowledged_at, a.resolved_at, a.status,
               j.origin_name, j.destination_name, u.name as user_name
        FROM alerts a
        JOIN journeys j ON a.journey_id = j.id
        JOIN users u ON j.user_id = u.id
        ORDER BY a.id DESC
    """)
    rows = cursor.fetchall()
    
    results = []
    for r in rows:
        item = dict(r)
        item["evidence"] = json.loads(item["evidence_json"]) if item["evidence_json"] else []
        # Get last known location
        cursor.execute("SELECT latitude, longitude, timestamp FROM trajectory_points WHERE journey_id = ? ORDER BY id DESC LIMIT 1", (item["journey_id"],))
        last_pt = cursor.fetchone()
        item["last_location"] = dict(last_pt) if last_pt else None
        results.append(item)

    conn.close()
    return results

@router.get("/{alert_id}")
def get_alert_detail(alert_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Alert not found")
    
    item = dict(row)
    item["evidence"] = json.loads(item["evidence_json"]) if item["evidence_json"] else []
    
    # Escalation chain status
    cursor.execute("""
        SELECT e.*, g.name as guardian_name, g.relationship, g.contact_masked
        FROM escalation_events e
        JOIN guardians g ON e.guardian_id = g.id
        WHERE e.alert_id = ?
        ORDER BY e.escalation_level ASC
    """, (alert_id,))
    item["escalation_events"] = [dict(e) for e in cursor.fetchall()]

    conn.close()
    return item

@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int):
    return EscalationService.acknowledge_alert(alert_id)

@router.post("/{alert_id}/resolve")
def resolve_alert(alert_id: int):
    return EscalationService.resolve_alert(alert_id)
