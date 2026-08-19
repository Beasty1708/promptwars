"""
Escalation Chain and Guardian Notification Service for Guardian AI
"""
from datetime import datetime, timezone
import json
from typing import Dict, Any, List, Optional
from ..db import get_db_connection

class EscalationService:
    @staticmethod
    def create_alert(
        journey_id: int,
        alert_type: str,
        severity: str,
        message: str,
        evidence: List[str]
    ) -> Dict[str, Any]:
        """Creates an alert record and dispatches escalation events to registered guardians."""
        conn = get_db_connection()
        cursor = conn.cursor()

        now_iso = datetime.now(timezone.utc).isoformat()
        evidence_json = json.dumps(evidence)

        cursor.execute("""
            INSERT INTO alerts (journey_id, alert_type, severity, message, evidence_json, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE')
        """, (journey_id, alert_type, severity, message, evidence_json, now_iso))
        alert_id = cursor.lastrowid

        # Fetch journey & user
        cursor.execute("SELECT user_id FROM journeys WHERE id = ?", (journey_id,))
        j_row = cursor.fetchone()
        user_id = j_row["user_id"] if j_row else 1

        # Fetch guardians ordered by priority (Primary = 1, Secondary = 2)
        cursor.execute("SELECT id, name, relationship, contact_masked, priority FROM guardians WHERE user_id = ? AND enabled = 1 ORDER BY priority ASC", (user_id,))
        guardians = cursor.fetchall()

        escalations = []
        for g in guardians:
            cursor.execute("""
                INSERT INTO escalation_events (alert_id, guardian_id, escalation_level, sent_at, status)
                VALUES (?, ?, ?, ?, 'SENT')
            """, (alert_id, g["id"], g["priority"], now_iso))
            escalations.append({
                "guardian_id": g["id"],
                "guardian_name": g["name"],
                "relationship": g["relationship"],
                "contact": g["contact_masked"],
                "level": g["priority"],
                "status": "SENT (Simulated Delivery)"
            })

        # Add audit log
        cursor.execute("""
            INSERT INTO audit_log (user_id, event_type, entity_type, entity_id, metadata_json, created_at)
            VALUES (?, 'GUARDIAN_ESCALATION_TRIGGERED', 'alert', ?, ?, ?)
        """, (user_id, alert_id, json.dumps({"alert_type": alert_type, "severity": severity}), now_iso))

        conn.commit()
        conn.close()

        return {
            "id": alert_id,
            "journey_id": journey_id,
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "evidence": evidence,
            "created_at": now_iso,
            "status": "ACTIVE",
            "escalations": escalations
        }

    @staticmethod
    def acknowledge_alert(alert_id: int) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        now_iso = datetime.now(timezone.utc).isoformat()

        cursor.execute("""
            UPDATE alerts
            SET acknowledged_at = ?, status = 'ACKNOWLEDGED'
            WHERE id = ?
        """, (now_iso, alert_id))

        cursor.execute("UPDATE escalation_events SET acknowledged_at = ?, status = 'ACKNOWLEDGED' WHERE alert_id = ?", (now_iso, alert_id))
        conn.commit()
        conn.close()
        return {"id": alert_id, "status": "ACKNOWLEDGED", "acknowledged_at": now_iso}

    @staticmethod
    def resolve_alert(alert_id: int) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        now_iso = datetime.now(timezone.utc).isoformat()

        cursor.execute("""
            UPDATE alerts
            SET resolved_at = ?, status = 'RESOLVED'
            WHERE id = ?
        """, (now_iso, alert_id))

        cursor.execute("SELECT journey_id FROM alerts WHERE id = ?", (alert_id,))
        r = cursor.fetchone()
        if r:
            cursor.execute("UPDATE journeys SET status = 'RESOLVED', tier = 'normal' WHERE id = ?", (r["journey_id"],))

        conn.commit()
        conn.close()
        return {"id": alert_id, "status": "RESOLVED", "resolved_at": now_iso}
