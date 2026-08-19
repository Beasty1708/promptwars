"""
Safety Check State Machine and Verification Service for Guardian AI
"""
from datetime import datetime, timezone
import json
from typing import Dict, Any, Optional
from ..db import get_db_connection
from .escalation_service import EscalationService

class SafetyCheckService:
    @staticmethod
    def create_safety_check(journey_id: int, timeout_sec: int = 60, evidence_summary: str = "") -> Dict[str, Any]:
        """Creates a pending safety check for a journey."""
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if there is already an active pending check
        cursor.execute("SELECT id, sent_at, timeout_sec, status FROM safety_checks WHERE journey_id = ? AND status = 'PENDING'", (journey_id,))
        existing = cursor.fetchone()
        if existing:
            conn.close()
            return dict(existing)

        now_iso = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO safety_checks (journey_id, sent_at, timeout_sec, status, evidence_summary)
            VALUES (?, ?, ?, 'PENDING', ?)
        """, (journey_id, now_iso, timeout_sec, evidence_summary))
        check_id = cursor.lastrowid

        # Update journey status to SAFETY_CHECK
        cursor.execute("UPDATE journeys SET status = 'SAFETY_CHECK' WHERE id = ?", (journey_id,))
        
        # Add audit log
        cursor.execute("""
            INSERT INTO audit_log (user_id, event_type, entity_type, entity_id, metadata_json, created_at)
            VALUES (1, 'SAFETY_CHECK_SENT', 'safety_check', ?, ?, ?)
        """, (check_id, json.dumps({"journey_id": journey_id, "timeout_sec": timeout_sec}), now_iso))

        conn.commit()
        conn.close()

        return {
            "id": check_id,
            "journey_id": journey_id,
            "sent_at": now_iso,
            "timeout_sec": timeout_sec,
            "status": "PENDING",
            "evidence_summary": evidence_summary
        }

    @staticmethod
    def handle_response(check_id: int, response_type: str) -> Dict[str, Any]:
        """
        Handles user response: 'safe', 'need_help', or 'cant_talk'.
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, journey_id, sent_at, timeout_sec, status FROM safety_checks WHERE id = ?", (check_id,))
        check = cursor.fetchone()
        if not check:
            conn.close()
            return {"error": "Safety check not found"}

        journey_id = check["journey_id"]
        now_iso = datetime.now(timezone.utc).isoformat()

        cursor.execute("""
            UPDATE safety_checks
            SET response = ?, responded_at = ?, status = 'RESPONDED'
            WHERE id = ?
        """, (response_type, now_iso, check_id))

        if response_type == "safe":
            # Resolves alert, updates journey to RESOLVED, sets safe confirmed
            cursor.execute("UPDATE journeys SET status = 'RESOLVED', final_concern_score = 15.0, tier = 'normal' WHERE id = ?", (journey_id,))
            cursor.execute("""
                INSERT INTO audit_log (user_id, event_type, entity_type, entity_id, metadata_json, created_at)
                VALUES (1, 'USER_CONFIRMED_SAFE', 'safety_check', ?, ?, ?)
            """, (check_id, json.dumps({"journey_id": journey_id}), now_iso))
            conn.commit()
            conn.close()
            return {"status": "RESOLVED", "message": "Safety confirmed. Learning recorded for this journey pattern."}

        elif response_type == "need_help":
            # Immediate Emergency Escalation
            cursor.execute("UPDATE journeys SET status = 'ESCALATED', final_concern_score = 100.0, tier = 'high_concern' WHERE id = ?", (journey_id,))
            conn.commit()
            conn.close()
            alert = EscalationService.create_alert(
                journey_id=journey_id,
                alert_type="EXPLICIT_HELP_REQUEST",
                severity="CRITICAL",
                message="User explicitly requested emergency assistance via safety prompt.",
                evidence=["User tapped 'I Need Help' button on safety check.", "Immediate escalation required."]
            )
            return {"status": "ESCALATED", "message": "Emergency escalation initiated.", "alert": alert}

        elif response_type == "cant_talk":
            cursor.execute("UPDATE journeys SET status = 'MONITOR', final_concern_score = 50.0, tier = 'monitor' WHERE id = ?", (journey_id,))
            cursor.execute("""
                INSERT INTO audit_log (user_id, event_type, entity_type, entity_id, metadata_json, created_at)
                VALUES (1, 'USER_CANT_TALK_SIGNAL', 'safety_check', ?, ?, ?)
            """, (check_id, json.dumps({"journey_id": journey_id}), now_iso))
            conn.commit()
            conn.close()
            return {"status": "MONITOR", "message": "Human presence confirmed. Maintaining elevated background monitoring."}

        conn.commit()
        conn.close()
        return {"status": "UNKNOWN"}

    @staticmethod
    def handle_timeout(check_id: int) -> Dict[str, Any]:
        """
        Handles timeout of safety check without user response.
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, journey_id, sent_at, status, evidence_summary FROM safety_checks WHERE id = ?", (check_id,))
        check = cursor.fetchone()
        if not check or check["status"] != "PENDING":
            conn.close()
            return {"error": "Check not found or already processed"}

        journey_id = check["journey_id"]
        now_iso = datetime.now(timezone.utc).isoformat()

        cursor.execute("UPDATE safety_checks SET status = 'TIMED_OUT' WHERE id = ?", (check_id,))
        cursor.execute("UPDATE journeys SET status = 'ESCALATED', tier = 'high_concern' WHERE id = ?", (journey_id,))
        
        conn.commit()
        conn.close()

        # Escalate to guardian
        evidence = [
            "Safety check sent to user received no response within 60 seconds.",
            check["evidence_summary"] or "Unexplained route deviation and prolonged dwell in high-risk sector."
        ]

        alert = EscalationService.create_alert(
            journey_id=journey_id,
            alert_type="SAFETY_CHECK_TIMEOUT",
            severity="HIGH",
            message="No response received to safety check within verification window. Escalating to guardians.",
            evidence=evidence
        )

        return {"status": "ESCALATED", "alert": alert}
