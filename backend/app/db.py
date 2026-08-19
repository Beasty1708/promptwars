"""
SQLite Database Connection and Initialization for Guardian AI
"""
import os
import sqlite3
from typing import Generator

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "guardian_ai.db"))

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def get_db():
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Create all schema tables if they do not already exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.executescript("""
    -- 1. Users
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone_masked TEXT NOT NULL,
        created_at TEXT NOT NULL,
        monitoring_enabled INTEGER DEFAULT 1
    );

    -- 2. Trusted Locations
    CREATE TABLE IF NOT EXISTS trusted_locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        type TEXT NOT NULL, -- home, university, work, gym, other
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        radius_m REAL DEFAULT 200.0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    -- 3. Guardians
    CREATE TABLE IF NOT EXISTS guardians (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        relationship TEXT NOT NULL,
        contact_masked TEXT NOT NULL,
        priority INTEGER DEFAULT 1, -- 1 = primary, 2 = secondary
        enabled INTEGER DEFAULT 1,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    -- 4. Journeys
    CREATE TABLE IF NOT EXISTS journeys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        origin_location_id INTEGER,
        destination_location_id INTEGER,
        origin_name TEXT,
        destination_name TEXT,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        expected_duration_sec INTEGER DEFAULT 1800,
        actual_duration_sec INTEGER DEFAULT 0,
        status TEXT DEFAULT 'IN_PROGRESS', -- IN_PROGRESS, COMPLETED, ANOMALY_DETECTED, SAFETY_CHECK, ESCALATED, RESOLVED
        anomaly_score REAL DEFAULT 0.0,
        environmental_score REAL DEFAULT 0.0,
        context_score REAL DEFAULT 0.0,
        final_concern_score REAL DEFAULT 0.0,
        tier TEXT DEFAULT 'normal',
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    -- 5. Trajectory Points
    CREATE TABLE IF NOT EXISTS trajectory_points (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        journey_id INTEGER NOT NULL,
        timestamp TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        speed_kmh REAL DEFAULT 25.0,
        heading REAL DEFAULT 0.0,
        stop_duration_sec INTEGER DEFAULT 0,
        FOREIGN KEY (journey_id) REFERENCES journeys(id) ON DELETE CASCADE
    );

    -- 6. Route Baselines
    CREATE TABLE IF NOT EXISTS route_baselines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        origin_location_id INTEGER,
        destination_location_id INTEGER,
        sample_count INTEGER DEFAULT 1,
        median_duration_sec INTEGER DEFAULT 1800,
        typical_departure_minute INTEGER DEFAULT 540, -- 09:00 AM
        typical_arrival_minute INTEGER DEFAULT 570,   -- 09:30 AM
        typical_speed_kmh REAL DEFAULT 28.0,
        encoded_route TEXT NOT NULL, -- JSON array of [lat, lon] waypoints
        route_variability REAL DEFAULT 50.0,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    -- 7. Context Events
    CREATE TABLE IF NOT EXISTS context_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        category TEXT NOT NULL, -- sports, concert, academic, transit, public_event
        venue TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        radius_m REAL DEFAULT 800.0,
        start_at TEXT NOT NULL,
        end_at TEXT NOT NULL,
        source TEXT DEFAULT 'local_registry',
        confidence REAL DEFAULT 0.90
    );

    -- 8. Anomaly Events
    CREATE TABLE IF NOT EXISTS anomaly_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        journey_id INTEGER NOT NULL,
        type TEXT NOT NULL, -- route_deviation, unexpected_stop, speed_anomaly, time_anomaly, destination_novelty, linger_post_event
        severity REAL NOT NULL,
        score REAL NOT NULL,
        evidence_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (journey_id) REFERENCES journeys(id) ON DELETE CASCADE
    );

    -- 9. Safety Checks
    CREATE TABLE IF NOT EXISTS safety_checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        journey_id INTEGER NOT NULL,
        sent_at TEXT NOT NULL,
        timeout_sec INTEGER DEFAULT 60,
        response TEXT, -- safe, need_help, cant_talk, null
        responded_at TEXT,
        status TEXT DEFAULT 'PENDING', -- PENDING, RESPONDED, TIMED_OUT, CANCELLED
        evidence_summary TEXT,
        FOREIGN KEY (journey_id) REFERENCES journeys(id) ON DELETE CASCADE
    );

    -- 10. Alerts
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        journey_id INTEGER NOT NULL,
        alert_type TEXT NOT NULL, -- SAFETY_CHECK_TIMEOUT, EXPLICIT_HELP_REQUEST, HIGH_CONCERN_UNEXPLAINED
        severity TEXT NOT NULL,   -- HIGH, CRITICAL
        message TEXT NOT NULL,
        evidence_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        acknowledged_at TEXT,
        resolved_at TEXT,
        status TEXT DEFAULT 'ACTIVE', -- ACTIVE, ACKNOWLEDGED, RESOLVED
        FOREIGN KEY (journey_id) REFERENCES journeys(id) ON DELETE CASCADE
    );

    -- 11. Escalation Events
    CREATE TABLE IF NOT EXISTS escalation_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_id INTEGER NOT NULL,
        guardian_id INTEGER NOT NULL,
        escalation_level INTEGER DEFAULT 1,
        sent_at TEXT NOT NULL,
        acknowledged_at TEXT,
        status TEXT DEFAULT 'SENT', -- SENT, DELIVERED, ACKNOWLEDGED
        FOREIGN KEY (alert_id) REFERENCES alerts(id) ON DELETE CASCADE,
        FOREIGN KEY (guardian_id) REFERENCES guardians(id) ON DELETE CASCADE
    );

    -- 12. Environmental Risk Points (created also in import_datasets.py)
    CREATE TABLE IF NOT EXISTS environmental_risk_points (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        city TEXT,
        area_name TEXT,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        lighting_score REAL DEFAULT 50.0,
        footfall_score REAL DEFAULT 50.0,
        cctv_score REAL DEFAULT 50.0,
        police_distance_km REAL DEFAULT 2.0,
        route_risk_score REAL DEFAULT 50.0,
        civic_deficit_score REAL DEFAULT 50.0,
        crime_risk_score REAL DEFAULT 50.0,
        confidence REAL DEFAULT 0.85
    );

    -- 13. Audit Log
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        event_type TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id INTEGER,
        metadata_json TEXT,
        created_at TEXT NOT NULL
    );

    -- Indices for high-speed queries
    CREATE INDEX IF NOT EXISTS idx_tp_journey ON trajectory_points(journey_id);
    CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
    CREATE INDEX IF NOT EXISTS idx_journeys_user ON journeys(user_id);
    CREATE INDEX IF NOT EXISTS idx_ctx_times ON context_events(start_at, end_at);
    CREATE INDEX IF NOT EXISTS idx_env_geo ON environmental_risk_points(latitude, longitude);
    """);

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database schema successfully initialized.")
