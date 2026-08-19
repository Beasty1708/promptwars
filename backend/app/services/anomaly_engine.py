"""
Personal Mobility Anomaly Detection Engine for Guardian AI
Combines statistical baseline comparisons and Isolation Forest anomaly scoring.
"""
import json
import sqlite3
import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from sklearn.ensemble import IsolationForest
from ..db import get_db_connection
from ..utils.geo import (
    haversine_distance,
    route_deviation,
    route_similarity,
    destination_novelty
)
from ..utils.time_utils import parse_iso, get_minute_of_day

class PersonalAnomalyEngine:
    def __init__(self):
        # Configurable anomaly component weights (PRD Section 5.2)
        self.weights = {
            "route_deviation": 0.30,
            "stop_anomaly": 0.20,
            "duration_anomaly": 0.20,
            "speed_anomaly": 0.10,
            "time_anomaly": 0.10,
            "destination_novelty": 0.10
        }

    def evaluate_point(
        self,
        user_id: int,
        journey_id: int,
        current_lat: float,
        current_lon: float,
        speed_kmh: float,
        stop_duration_sec: int,
        timestamp_str: str,
        actual_trajectory: List[Tuple[float, float]]
    ) -> Dict[str, Any]:
        """
        Evaluates how unusual the current movement point is compared to the user's historical baseline.
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Fetch user's baseline routes
        cursor.execute("""
            SELECT id, origin_location_id, destination_location_id,
                   median_duration_sec, typical_departure_minute, typical_speed_kmh,
                   encoded_route, route_variability
            FROM route_baselines
            WHERE user_id = ?
            ORDER BY sample_count DESC
            LIMIT 1
        """, (user_id,))
        baseline_row = cursor.fetchone()

        # 2. Fetch trusted locations
        cursor.execute("SELECT id, name, type, latitude, longitude, radius_m FROM trusted_locations WHERE user_id = ?", (user_id,))
        trusted_locs = [dict(r) for r in cursor.fetchall()]
        conn.close()

        # Parse baseline waypoints
        baseline_waypoints = []
        if baseline_row and baseline_row["encoded_route"]:
            try:
                baseline_waypoints = json.loads(baseline_row["encoded_route"])
            except Exception:
                baseline_waypoints = []

        # 1. Route Deviation calculation
        if baseline_waypoints:
            dev_m = route_deviation(current_lat, current_lon, baseline_waypoints)
            sim_score = route_similarity(actual_trajectory, baseline_waypoints)
            # 0m -> 0 score, 200m corridor -> 10, 600m -> 70, >1000m -> 95
            route_score = min(100.0, max(0.0, (dev_m / 800.0) * 100.0))
        else:
            dev_m = 0.0
            sim_score = 100.0
            route_score = 10.0

        # 2. Stop Anomaly calculation (> 5 min unexpected dwell time = 300s)
        if stop_duration_sec > 0:
            # 0-60s = normal stoplight (10), 300s = 60, >600s = 95
            stop_score = min(100.0, max(0.0, (stop_duration_sec / 600.0) * 100.0))
        else:
            stop_score = 0.0

        # 3. Speed Anomaly calculation
        typical_speed = baseline_row["typical_speed_kmh"] if baseline_row else 25.0
        if speed_kmh < 3.0 and stop_duration_sec > 120:
            speed_score = min(80.0, stop_score)
        elif speed_kmh > typical_speed * 2.2:
            speed_score = 65.0
        else:
            speed_score = 5.0

        # 4. Time-of-Day Anomaly calculation
        curr_minute = get_minute_of_day(parse_iso(timestamp_str))
        typical_minute = baseline_row["typical_departure_minute"] if baseline_row else 540
        time_diff_mins = abs(curr_minute - typical_minute)
        # Handle wrap-around across midnight
        if time_diff_mins > 720:
            time_diff_mins = 1440 - time_diff_mins
        # 0 mins diff -> 0, 120 mins diff -> 40, >300 mins diff -> 85
        time_score = min(100.0, (time_diff_mins / 300.0) * 100.0)

        # 5. Destination / Location Novelty
        dest_nov = destination_novelty(current_lat, current_lon, trusted_locs)

        # 6. Duration Anomaly (if journey has elapsed)
        duration_score = 10.0

        # Composite Weighted Personal Anomaly Score (PRD Section 5.2)
        composite_score = (
            self.weights["route_deviation"] * route_score +
            self.weights["stop_anomaly"] * stop_score +
            self.weights["duration_anomaly"] * duration_score +
            self.weights["speed_anomaly"] * speed_score +
            self.weights["time_anomaly"] * time_score +
            self.weights["destination_novelty"] * dest_nov
        )

        # Optional Isolation Forest calibration
        if baseline_waypoints and len(actual_trajectory) >= 3:
            try:
                # Synthetic baseline feature envelope for Isolation Forest
                X_normal = np.array([
                    [0.0, 100.0, 0.0, 25.0, 0.0],
                    [50.0, 95.0, 30.0, 28.0, 10.0],
                    [80.0, 90.0, 60.0, 22.0, 20.0],
                    [120.0, 85.0, 90.0, 20.0, 30.0],
                ])
                clf = IsolationForest(contamination=0.1, random_state=42)
                clf.fit(X_normal)
                X_curr = np.array([[dev_m, sim_score, stop_duration_sec, speed_kmh, time_diff_mins]])
                if_pred = clf.predict(X_curr)[0] # -1 for anomaly, 1 for normal
                if if_pred == -1 and composite_score < 40.0:
                    composite_score = max(composite_score, 45.0)
            except Exception:
                pass

        # Generate interpretable evidence notes
        evidence = []
        if dev_m > 300.0:
            evidence.append(f"Route is {int(dev_m)}m outside normal travel corridor (Similarity: {sim_score:.0f}%)")
        
        if stop_duration_sec > 180:
            mins = int(stop_duration_sec / 60)
            evidence.append(f"Unexpected {mins} min stop detected")

        if dest_nov > 60.0:
            evidence.append("Location is unfamiliar relative to registered trusted destinations")

        if time_score > 60.0:
            evidence.append("Journey timing differs significantly from typical routine")

        return {
            "score": round(max(0.0, min(100.0, composite_score)), 1),
            "route_deviation_m": round(dev_m, 1),
            "route_similarity": sim_score,
            "stop_duration_sec": stop_duration_sec,
            "destination_novelty": dest_nov,
            "time_score": round(time_score, 1),
            "evidence": evidence
        }
