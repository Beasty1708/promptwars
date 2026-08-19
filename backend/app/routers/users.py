"""
User, Trusted Locations, and Guardians API Router
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from ..db import get_db_connection
from ..schemas import (
    UserResponse, TrustedLocationBase, TrustedLocationCreate, TrustedLocationResponse,
    GuardianBase, GuardianCreate, GuardianResponse
)

router = APIRouter(prefix="/api/users", tags=["Users"])

@router.get("/{user_id}", response_model=UserResponse)
def get_user_profile(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, phone_masked, created_at, monitoring_enabled FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row)

@router.post("/{user_id}/toggle-monitoring")
def toggle_monitoring(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT monitoring_enabled FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    new_state = 0 if row["monitoring_enabled"] else 1
    cursor.execute("UPDATE users SET monitoring_enabled = ? WHERE id = ?", (new_state, user_id))
    conn.commit()
    conn.close()
    return {"user_id": user_id, "monitoring_enabled": bool(new_state)}

@router.get("/{user_id}/locations", response_model=List[TrustedLocationResponse])
def get_trusted_locations(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trusted_locations WHERE user_id = ? ORDER BY id ASC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.post("/{user_id}/locations", response_model=TrustedLocationResponse)
def add_trusted_location(user_id: int, payload: TrustedLocationBase):
    conn = get_db_connection()
    cursor = conn.cursor()
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor.execute("""
        INSERT INTO trusted_locations (user_id, name, type, latitude, longitude, radius_m, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, payload.name, payload.type, payload.latitude, payload.longitude, payload.radius_m, now_iso))
    loc_id = cursor.lastrowid
    conn.commit()
    cursor.execute("SELECT * FROM trusted_locations WHERE id = ?", (loc_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row)

@router.delete("/{user_id}/locations/{loc_id}")
def delete_trusted_location(user_id: int, loc_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trusted_locations WHERE id = ? AND user_id = ?", (loc_id, user_id))
    conn.commit()
    conn.close()
    return {"status": "DELETED", "id": loc_id}

@router.get("/{user_id}/guardians", response_model=List[GuardianResponse])
def get_guardians(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM guardians WHERE user_id = ? ORDER BY priority ASC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.post("/{user_id}/guardians", response_model=GuardianResponse)
def add_guardian(user_id: int, payload: GuardianBase):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO guardians (user_id, name, relationship, contact_masked, priority, enabled)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, payload.name, payload.relationship, payload.contact_masked, payload.priority, 1 if payload.enabled else 0))
    g_id = cursor.lastrowid
    conn.commit()
    cursor.execute("SELECT * FROM guardians WHERE id = ?", (g_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row)

@router.delete("/{user_id}/data")
def delete_user_history(user_id: int):
    """Privacy requirement: delete personal history and trajectory audit records."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trajectory_points WHERE journey_id IN (SELECT id FROM journeys WHERE user_id = ?)", (user_id,))
    cursor.execute("DELETE FROM safety_checks WHERE journey_id IN (SELECT id FROM journeys WHERE user_id = ?)", (user_id,))
    cursor.execute("DELETE FROM alerts WHERE journey_id IN (SELECT id FROM journeys WHERE user_id = ?)", (user_id,))
    cursor.execute("DELETE FROM journeys WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM audit_log WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"status": "CLEARED", "message": "All personal journey and trajectory data deleted in compliance with privacy policy."}
