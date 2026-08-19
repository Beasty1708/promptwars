"""
Journey Lifecycle and Trajectory Tracking Service for Guardian AI
"""
from datetime import datetime, timezone, timedelta
import json
import sqlite3
from typing import Dict, Any, List, Optional, Tuple
from ..db import get_db_connection
from .risk_engine import RiskEngine
from .safety_check_service import SafetyCheckService

class JourneyService:
    def __init__(self):
        self.risk_engine = RiskEngine()

    def start_journey(
        self,
        user_id: int = 1,
        origin_name: str = "Home",
        destination_name: str = "University Campus",
        expected_duration_sec: int = 1800,
        custom_start_time: Optional[str] = None
    ) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()

        started_at = custom_start_time or datetime.now(timezone.utc).isoformat()

        cursor.execute("""
            INSERT INTO journeys (
                user_id, origin_name, destination_name, started_at,
                expected_duration_sec, actual_duration_sec, status,
                anomaly_score, environmental_score, context_score, final_concern_score, tier
            ) VALUES (?, ?, ?, ?, ?, 0, 'IN_PROGRESS', 0.0, 20.0, 10.0, 10.0, 'normal')
        """, (user_id, origin_name, destination_name, started_at, expected_duration_sec))
        journey_id = cursor.lastrowid

        # Record audit log
        cursor.execute("""
            INSERT INTO audit_log (user_id, event_type, entity_type, entity_id, metadata_json, created_at)
            VALUES (?, 'JOURNEY_STARTED', 'journey', ?, ?, ?)
        """, (user_id, journey_id, json.dumps({"origin": origin_name, "destination": destination_name}), started_at))

        conn.commit()
        conn.close()

        return self.get_journey(journey_id)

    def add_point(
        self,
        journey_id: int,
        latitude: float,
        longitude: float,
        speed_kmh: float = 25.0,
        heading: float = 0.0,
        stop_duration_sec: int = 0,
        timestamp_str: Optional[str] = None,
        is_safe_confirmed: bool = False,
        is_help_requested: bool = False
    ) -> Dict[str, Any]:
        """
        Records a new GPS point along the journey and evaluates real-time safety risk.
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, user_id, started_at, status FROM journeys WHERE id = ?", (journey_id,))
        journey = cursor.fetchone()
        if not journey:
            conn.close()
            return {"error": "Journey not found"}

        now_ts = timestamp_str or datetime.now(timezone.utc).isoformat()

        # Insert trajectory point
        cursor.execute("""
            INSERT INTO trajectory_points (journey_id, timestamp, latitude, longitude, speed_kmh, heading, stop_duration_sec)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (journey_id, now_ts, latitude, longitude, speed_kmh, heading, stop_duration_sec))

        # Fetch full trajectory so far for similarity & spatial evaluation
        cursor.execute("SELECT latitude, longitude FROM trajectory_points WHERE journey_id = ? ORDER BY id ASC", (journey_id,))
        traj_points = [(r["latitude"], r["longitude"]) for r in cursor.fetchall()]
        conn.close()

        # Evaluate risk state
        risk = self.risk_engine.evaluate_journey_state(
            user_id=journey["user_id"],
            journey_id=journey_id,
            current_lat=latitude,
            current_lon=longitude,
            speed_kmh=speed_kmh,
            stop_duration_sec=stop_duration_sec,
            timestamp_str=now_ts,
            actual_trajectory=traj_points,
            is_safe_confirmed=is_safe_confirmed,
            is_help_requested=is_help_requested
        )

        # Update journey record with latest scores
        conn = get_db_connection()
        cursor = conn.cursor()

        new_status = journey["status"]
        if journey["status"] not in ("ESCALATED", "RESOLVED"):
            if risk["tier"] in ("safety_check", "high_concern"):
                new_status = "SAFETY_CHECK"
            elif risk["tier"] == "monitor":
                new_status = "MONITOR"
            else:
                new_status = "IN_PROGRESS"

        cursor.execute("""
            UPDATE journeys
            SET anomaly_score = ?,
                environmental_score = ?,
                context_score = ?,
                final_concern_score = ?,
                tier = ?,
                status = ?
            WHERE id = ?
        """, (
            risk["personal_anomaly"],
            risk["environmental_risk"],
            risk["context_explanation"],
            risk["final_concern"],
            risk["tier"],
            new_status,
            journey_id
        ))
        conn.commit()
        conn.close()

        # Automatically spawn safety check if concern reaches threshold and none is active
        active_safety_check = None
        if risk["tier"] in ("safety_check", "high_concern") and journey["status"] != "RESOLVED":
            summary = "; ".join(risk["evidence"][:2])
            active_safety_check = SafetyCheckService.create_safety_check(journey_id, timeout_sec=60, evidence_summary=summary)

        return {
            "journey_id": journey_id,
            "point": {
                "latitude": latitude,
                "longitude": longitude,
                "speed_kmh": speed_kmh,
                "stop_duration_sec": stop_duration_sec,
                "timestamp": now_ts
            },
            "risk": risk,
            "safety_check": active_safety_check
        }

    def get_journey(self, journey_id: int) -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM journeys WHERE id = ?", (journey_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        journey = dict(row)

        # Fetch trajectory points
        cursor.execute("SELECT * FROM trajectory_points WHERE journey_id = ? ORDER BY id ASC", (journey_id,))
        journey["trajectory"] = [dict(p) for p in cursor.fetchall()]

        # Fetch active safety check if any
        cursor.execute("SELECT * FROM safety_checks WHERE journey_id = ? ORDER BY id DESC LIMIT 1", (journey_id,))
        sc = cursor.fetchone()
        journey["active_safety_check"] = dict(sc) if sc else None

        # Fetch active alerts if any
        cursor.execute("SELECT * FROM alerts WHERE journey_id = ? ORDER BY id DESC LIMIT 1", (journey_id,))
        al = cursor.fetchone()
        if al:
            al_dict = dict(al)
            al_dict["evidence"] = json.loads(al_dict["evidence_json"]) if al_dict["evidence_json"] else []
            journey["active_alert"] = al_dict
        else:
            journey["active_alert"] = None

        conn.close()
        return journey

    def finish_journey(self, journey_id: int) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        now_iso = datetime.now(timezone.utc).isoformat()
        cursor.execute("UPDATE journeys SET finished_at = ?, status = 'COMPLETED' WHERE id = ?", (now_iso, journey_id))
        conn.commit()
        conn.close()
        return self.get_journey(journey_id)
