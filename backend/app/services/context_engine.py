"""
Context Intelligence Engine for Guardian AI
Evaluates whether real-world scheduled events (matches, concerts, academic events, transit)
explain an unusual location or movement pattern.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import sqlite3
from ..db import get_db_connection
from ..utils.geo import haversine_distance
from ..utils.time_utils import parse_iso, temporal_overlap_score

class BaseContextProvider(ABC):
    @abstractmethod
    def find_context(self, latitude: float, longitude: float, timestamp_str: str) -> List[Dict[str, Any]]:
        pass

class LocalEventProvider(BaseContextProvider):
    def find_context(self, latitude: float, longitude: float, timestamp_str: str) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, category, venue, latitude, longitude, radius_m, start_at, end_at, source, confidence
            FROM context_events
        """)
        events = cursor.fetchall()
        conn.close()

        matched = []
        for ev in events:
            dist = haversine_distance(latitude, longitude, ev["latitude"], ev["longitude"])
            if dist <= ev["radius_m"]:
                expl_score, mismatch_score, time_reason = temporal_overlap_score(
                    timestamp_str, ev["start_at"], ev["end_at"]
                )
                matched.append({
                    "event_id": ev["id"],
                    "title": ev["title"],
                    "category": ev["category"],
                    "venue": ev["venue"],
                    "distance_m": round(dist, 1),
                    "start_at": ev["start_at"],
                    "end_at": ev["end_at"],
                    "explanation_score": expl_score,
                    "mismatch_score": mismatch_score,
                    "temporal_reason": time_reason,
                    "confidence": ev["confidence"]
                })

        return matched

class SportsEventProvider(BaseContextProvider):
    """Specialized sports fixture provider."""
    def find_context(self, latitude: float, longitude: float, timestamp_str: str) -> List[Dict[str, Any]]:
        local = LocalEventProvider()
        events = local.find_context(latitude, longitude, timestamp_str)
        return [e for e in events if e["category"] in ("sports", "football", "cricket")]

class ContextEngine:
    def __init__(self):
        self.providers: List[BaseContextProvider] = [
            LocalEventProvider(),
            SportsEventProvider()
        ]

    def evaluate_context(self, latitude: float, longitude: float, timestamp_str: str) -> Dict[str, Any]:
        """
        Main context reasoning method.
        Returns:
          explanation_score: 0 - 100 (how well context legitimizes the presence)
          mismatch_score: 0 - 100 (how unexplainable/suspicious the lingering is)
          matched_event: Optional dict
          evidence: List[str]
        """
        all_matches = []
        for provider in self.providers:
            matches = provider.find_context(latitude, longitude, timestamp_str)
            for m in matches:
                if not any(existing["event_id"] == m["event_id"] for existing in all_matches):
                    all_matches.append(m)

        if not all_matches:
            return {
                "explanation_score": 0.0,
                "mismatch_score": 50.0,
                "matched_event": None,
                "has_context": False,
                "evidence": ["No scheduled public event or verified destination found at this location."]
            }

        # Select highest explanation or highest relevant match
        best_match = max(all_matches, key=lambda x: x["explanation_score"])
        
        evidence = []
        evidence.append(f"Scheduled {best_match['category']}: '{best_match['title']}' at {best_match['venue']}.")
        evidence.append(best_match["temporal_reason"])

        if best_match["explanation_score"] >= 60.0:
            evidence.append("Event schedule strongly explains current presence.")
        elif best_match["mismatch_score"] >= 60.0:
            evidence.append("Post-event lingering exceeds typical dispersal window.")

        return {
            "explanation_score": best_match["explanation_score"],
            "mismatch_score": best_match["mismatch_score"],
            "matched_event": best_match,
            "has_context": True,
            "evidence": evidence
        }
