#!/usr/bin/env python3
"""
Database Seeding Script for Guardian AI
Creates demo user, trusted locations, guardians, route baselines, context events, and initial baseline states.
"""
import os
import sys
import json
import sqlite3
from datetime import datetime, timezone

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "guardian_ai.db"))

def seed_demo():
    print("=" * 60)
    print(" GUARDIAN AI — SEED DEMO DATABASE")
    print("=" * 60)

    # Initialize tables if needed
    from backend.app.db import init_db
    init_db()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    today_date = datetime.now().strftime("%Y-%m-%d")

    # 1. Clear old user / journey demo records (preserve environmental risk points)
    cursor.execute("DELETE FROM users")
    cursor.execute("DELETE FROM trusted_locations")
    cursor.execute("DELETE FROM guardians")
    cursor.execute("DELETE FROM route_baselines")
    cursor.execute("DELETE FROM context_events")
    cursor.execute("DELETE FROM journeys")
    cursor.execute("DELETE FROM trajectory_points")
    cursor.execute("DELETE FROM safety_checks")
    cursor.execute("DELETE FROM alerts")
    cursor.execute("DELETE FROM escalation_events")
    cursor.execute("DELETE FROM audit_log")

    # 2. Demo User
    cursor.execute("""
        INSERT INTO users (id, name, phone_masked, created_at, monitoring_enabled)
        VALUES (1, 'Alex Rivera', '+91 XXXXX X4321', ?, 1)
    """, (now_iso,))
    print("[SEEDED] User: Alex Rivera")

    # 3. Trusted Locations
    trusted_locations = [
        (1, 1, 'Home (Central Delhi)', 'home', 28.6139, 77.2090, 250.0, now_iso),
        (2, 1, 'University Campus (IIT/JNU Gate)', 'university', 28.5450, 77.1926, 300.0, now_iso),
        (3, 1, 'City Tech Hub (Nehru Place)', 'work', 28.5500, 77.2500, 300.0, now_iso),
        (4, 1, 'National Stadium (JLN)', 'other', 28.5830, 77.2340, 400.0, now_iso)
    ]
    cursor.executemany("""
        INSERT INTO trusted_locations (id, user_id, name, type, latitude, longitude, radius_m, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, trusted_locations)
    print(f"[SEEDED] {len(trusted_locations)} Trusted Locations.")

    # 4. Guardians
    guardians = [
        (1, 1, 'Sarah Rivera', 'Mother (Primary)', '+91 XXXXX X9901', 1, 1),
        (2, 1, 'Jordan Lee', 'Close Friend / Roommate', '+91 XXXXX X8822', 2, 1)
    ]
    cursor.executemany("""
        INSERT INTO guardians (id, user_id, name, relationship, contact_masked, priority, enabled)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, guardians)
    print(f"[SEEDED] {len(guardians)} Guardians.")

    # 5. Baseline Route (Home -> University Campus)
    normal_waypoints = [
        [28.6139, 77.2090], # Home
        [28.6050, 77.2060],
        [28.5950, 77.2020],
        [28.5850, 77.1980],
        [28.5700, 77.1950], # Ring Road
        [28.5550, 77.1935],
        [28.5450, 77.1926]  # University
    ]

    cursor.execute("""
        INSERT INTO route_baselines (
            id, user_id, origin_location_id, destination_location_id,
            sample_count, median_duration_sec, typical_departure_minute,
            typical_arrival_minute, typical_speed_kmh, encoded_route, route_variability
        ) VALUES (1, 1, 1, 2, 24, 1680, 540, 568, 26.5, ?, 45.0)
    """, (json.dumps(normal_waypoints),))
    print("[SEEDED] Route Baseline (Home -> University Campus, 24 previous journeys).")

    # 6. Context Events
    events = [
        (
            1, "ISL Football Championship: Delhi Dynamos vs Mumbai FC",
            "sports", "Jawaharlal Nehru National Stadium Arena",
            28.5830, 77.2340, 900.0,
            f"{today_date}T14:00:00", f"{today_date}T16:00:00",
            "Delhi Sports Authority & Match Calendar", 0.96
        ),
        (
            2, "Sunburn Live Acoustic Music Concert",
            "concert", "Talkatora Open Air Gardens",
            28.6210, 77.1940, 750.0,
            f"{today_date}T19:00:00", f"{today_date}T22:30:00",
            "City Events & Ticket Registry", 0.92
        ),
        (
            3, "National AI & Autonomous Systems Symposium",
            "academic", "University Campus Main Auditorium",
            28.5450, 77.1926, 600.0,
            f"{today_date}T09:00:00", f"{today_date}T17:00:00",
            "Campus Academic Schedule", 0.98
        ),
        (
            4, "Express International Flight AI-302",
            "transit", "Indira Gandhi International Airport T3",
            28.5562, 77.1000, 1500.0,
            f"{today_date}T06:00:00", f"{today_date}T08:30:00",
            "Aviation Flight Data Feed", 0.95
        )
    ]

    cursor.executemany("""
        INSERT INTO context_events (id, title, category, venue, latitude, longitude, radius_m, start_at, end_at, source, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, events)
    print(f"[SEEDED] {len(events)} Context Events.")

    conn.commit()
    conn.close()

    # 7. Initial default journey in Normal state for startup UI
    from backend.app.services.simulation_service import SimulationService
    sim = SimulationService()
    sim.run_scenario("normal", user_id=1)
    print("[SEEDED] Initialized active demo journey in Normal state.")

    print("=" * 60)
    print("[SUCCESS] Database seeding completed successfully.")

if __name__ == "__main__":
    seed_demo()
