"""
Environmental Safety and Infrastructure Context Service for Guardian AI
Integrates data from the four supplied datasets (Streetlight, Road, Crime, Delhi/Mumbai Crime).
"""
import sqlite3
from typing import Dict, Any, List, Tuple
from ..db import get_db_connection
from ..utils.geo import haversine_distance

class EnvironmentService:
    @staticmethod
    def get_environmental_risk(latitude: float, longitude: float, search_radius_m: float = 1200.0) -> Dict[str, Any]:
        """
        Calculates environmental risk score (0 - 100) around a given GPS coordinate.
        Integrates lighting, footfall, CCTV surveillance, police proximity, civic deficit, and historical crime.
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        # Bounding box filter for query performance (~0.015 degrees ~= 1.5 km)
        lat_delta = search_radius_m / 111000.0
        lon_delta = search_radius_m / (111000.0 * 0.88)

        cursor.execute("""
            SELECT id, source, city, area_name, latitude, longitude,
                   lighting_score, footfall_score, cctv_score, police_distance_km,
                   route_risk_score, civic_deficit_score, crime_risk_score
            FROM environmental_risk_points
            WHERE latitude BETWEEN ? AND ?
              AND longitude BETWEEN ? AND ?
        """, (latitude - lat_delta, latitude + lat_delta, longitude - lon_delta, longitude + lon_delta))

        rows = cursor.fetchall()
        conn.close()

        # Find neighboring points with inverse distance weighting
        neighbors = []
        for r in rows:
            dist = haversine_distance(latitude, longitude, r["latitude"], r["longitude"])
            if dist <= search_radius_m:
                neighbors.append((dist, r))

        # Fallback if no exact points within radius: find single closest point
        if not neighbors:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, source, city, area_name, latitude, longitude,
                       lighting_score, footfall_score, cctv_score, police_distance_km,
                       route_risk_score, civic_deficit_score, crime_risk_score
                FROM environmental_risk_points
                ORDER BY ((latitude - ?) * (latitude - ?) + (longitude - ?) * (longitude - ?)) ASC
                LIMIT 3
            """, (latitude, latitude, longitude, longitude))
            fallback_rows = cursor.fetchall()
            conn.close()
            for r in fallback_rows:
                dist = haversine_distance(latitude, longitude, r["latitude"], r["longitude"])
                neighbors.append((dist, r))

        if not neighbors:
            return {
                "score": 30.0,
                "lighting_score": 70.0,
                "footfall_score": 60.0,
                "cctv_score": 50.0,
                "police_distance_km": 2.0,
                "crime_risk_score": 30.0,
                "evidence": ["Environmental baseline: Average urban safety factors."]
            }

        # Weighted aggregate
        total_weight = 0.0
        weighted_lighting = 0.0
        weighted_footfall = 0.0
        weighted_cctv = 0.0
        weighted_police_dist = 0.0
        weighted_route_risk = 0.0
        weighted_civic_deficit = 0.0
        weighted_crime_risk = 0.0

        for dist, r in neighbors:
            w = 1.0 / (max(dist, 20.0) ** 1.2)
            total_weight += w
            weighted_lighting += r["lighting_score"] * w
            weighted_footfall += r["footfall_score"] * w
            weighted_cctv += r["cctv_score"] * w
            weighted_police_dist += r["police_distance_km"] * w
            weighted_route_risk += r["route_risk_score"] * w
            weighted_civic_deficit += r["civic_deficit_score"] * w
            weighted_crime_risk += r["crime_risk_score"] * w

        avg_lighting = weighted_lighting / total_weight
        avg_footfall = weighted_footfall / total_weight
        avg_cctv = weighted_cctv / total_weight
        avg_police_dist = weighted_police_dist / total_weight
        avg_route_risk = weighted_route_risk / total_weight
        avg_civic_deficit = weighted_civic_deficit / total_weight
        avg_crime_risk = weighted_crime_risk / total_weight

        # Environmental risk component weights (PRD Section 5.2)
        # Lighting deficit (100 - lighting): 15%
        # Footfall deficit (100 - footfall): 15%
        # CCTV deficit (100 - cctv): 10%
        # Police proximity (dist / 5km * 100): 10%
        # Route risk: 10%
        # Civic deficit: 10%
        # Crime/historical incident risk: 30%
        
        light_deficit = max(0.0, 100.0 - avg_lighting)
        footfall_deficit = max(0.0, 100.0 - avg_footfall)
        cctv_deficit = max(0.0, 100.0 - avg_cctv)
        police_risk = min(100.0, (avg_police_dist / 4.0) * 100.0)

        composite_env_risk = (
            0.30 * avg_crime_risk +
            0.15 * light_deficit +
            0.10 * cctv_deficit +
            0.15 * footfall_deficit +
            0.10 * avg_civic_deficit +
            0.10 * police_risk +
            0.10 * avg_route_risk
        )

        # Generate interpretable evidence notes
        evidence = []
        if avg_lighting < 40.0:
            evidence.append(f"Area lighting is poor ({avg_lighting:.0f}/100 quality)")
        elif avg_lighting > 75.0:
            evidence.append(f"Area is well lit ({avg_lighting:.0f}/100 quality)")

        if avg_footfall < 35.0:
            evidence.append(f"Low footfall / bystander density observed")
        elif avg_footfall > 70.0:
            evidence.append(f"Active public presence / high footfall")

        if avg_cctv < 30.0:
            evidence.append("CCTV surveillance sparse or absent")

        if avg_police_dist > 3.0:
            evidence.append(f"Nearest police facility is {avg_police_dist:.1f} km away")

        if avg_crime_risk > 65.0:
            evidence.append("Historical incident tracking indicates elevated contextual risk in sector")

        return {
            "score": round(max(5.0, min(95.0, composite_env_risk)), 1),
            "lighting_score": round(avg_lighting, 1),
            "footfall_score": round(avg_footfall, 1),
            "cctv_score": round(avg_cctv, 1),
            "police_distance_km": round(avg_police_dist, 1),
            "route_risk_score": round(avg_route_risk, 1),
            "civic_deficit_score": round(avg_civic_deficit, 1),
            "crime_risk_score": round(avg_crime_risk, 1),
            "evidence": evidence
        }
