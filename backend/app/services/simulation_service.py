"""
Journey Simulation Service for Guardian AI
Generates pre-configured realistic trajectories and handles stepped anomaly injection for judges and demo flows.
"""
from datetime import datetime, timezone, timedelta
import json
from typing import Dict, Any, List, Optional
from ..db import get_db_connection
from .journey_service import JourneyService
from .safety_check_service import SafetyCheckService
from .escalation_service import EscalationService

# Key Geo Waypoints in Delhi NCR Demo Map
LOC_HOME = (28.6139, 77.2090)      # Central Delhi Home
LOC_UNIVERSITY = (28.5450, 77.1926) # University Campus Main Gate
LOC_STADIUM = (28.5830, 77.2340)    # National Stadium Arena
LOC_STADIUM_ALLEY = (28.5860, 77.2390) # Dark Outer Alley behind Stadium

# Corridor 1: Home to University (Normal Commute)
ROUTE_NORMAL_CORRIDOR = [
    (28.6139, 77.2090), # Home
    (28.6050, 77.2060),
    (28.5950, 77.2020),
    (28.5850, 77.1980),
    (28.5700, 77.1950), # IIT / Ring Road
    (28.5550, 77.1935),
    (28.5450, 77.1926)  # University
]

# Corridor 2: Deviation towards Stadium
ROUTE_STADIUM_DEVIATION = [
    (28.6139, 77.2090), # Home
    (28.6050, 77.2150), # Turning East away from college corridor
    (28.5980, 77.2220), # India Gate bypass
    (28.5900, 77.2280), # JLN flyover
    (28.5830, 77.2340)  # Arrive Stadium
]

# Corridor 3: Lingering into dark alley after event
ROUTE_POST_EVENT_ALLEY = [
    (28.5830, 77.2340), # Stadium Main
    (28.5845, 77.2365), # Outer parking
    (28.5860, 77.2390)  # Unlit back alley
]

class SimulationService:
    def __init__(self):
        self.journey_service = JourneyService()

    def run_scenario(self, scenario_name: str, user_id: int = 1) -> Dict[str, Any]:
        """
        Runs one of the 6 canonical PRD scenarios.
        """
        now = datetime.now()

        if scenario_name == "normal":
            # Scenario 1: Normal Journey Home -> University
            start_time = now.replace(hour=9, minute=0, second=0).isoformat()
            journey = self.journey_service.start_journey(
                user_id=user_id,
                origin_name="Home",
                destination_name="University Campus",
                custom_start_time=start_time
            )
            journey_id = journey["id"]

            curr_dt = now.replace(hour=9, minute=0, second=0)
            for i, (lat, lon) in enumerate(ROUTE_NORMAL_CORRIDOR):
                curr_dt += timedelta(minutes=4)
                self.journey_service.add_point(
                    journey_id=journey_id,
                    latitude=lat,
                    longitude=lon,
                    speed_kmh=26.0,
                    stop_duration_sec=0,
                    timestamp_str=curr_dt.isoformat()
                )

            return {
                "scenario": "normal",
                "title": "Demo 1: Normal Commute",
                "description": "User travels along registered Home -> University corridor. AI verifies normal pattern.",
                "journey": self.journey_service.get_journey(journey_id)
            }

        elif scenario_name == "stadium_deviation":
            # Scenario 2: Detour to Stadium during active Match (14:00 - 16:00)
            start_time = now.replace(hour=14, minute=10, second=0).isoformat()
            journey = self.journey_service.start_journey(
                user_id=user_id,
                origin_name="Home",
                destination_name="National Stadium",
                custom_start_time=start_time
            )
            journey_id = journey["id"]

            curr_dt = now.replace(hour=14, minute=10, second=0)
            for lat, lon in ROUTE_STADIUM_DEVIATION:
                curr_dt += timedelta(minutes=5)
                self.journey_service.add_point(
                    journey_id=journey_id,
                    latitude=lat,
                    longitude=lon,
                    speed_kmh=24.0,
                    stop_duration_sec=0,
                    timestamp_str=curr_dt.isoformat()
                )

            return {
                "scenario": "stadium_deviation",
                "title": "Demo 2: Legitimate Stadium Visit (Context Explained)",
                "description": "User deviates to Stadium. AI detects football match (14:00-16:00) and suppresses false alarm.",
                "journey": self.journey_service.get_journey(journey_id)
            }

        elif scenario_name == "post_event_anomaly":
            # Scenario 3: Match ended at 16:00, user remains until 17:45 in dark alley
            start_time = now.replace(hour=14, minute=15, second=0).isoformat()
            journey = self.journey_service.start_journey(
                user_id=user_id,
                origin_name="Home",
                destination_name="National Stadium",
                custom_start_time=start_time
            )
            journey_id = journey["id"]

            # Initial travel
            curr_dt = now.replace(hour=14, minute=15, second=0)
            for lat, lon in ROUTE_STADIUM_DEVIATION:
                curr_dt += timedelta(minutes=4)
                self.journey_service.add_point(
                    journey_id=journey_id,
                    latitude=lat,
                    longitude=lon,
                    speed_kmh=25.0,
                    stop_duration_sec=0,
                    timestamp_str=curr_dt.isoformat()
                )

            # Advance clock to 17:45 (1h45m post-match) and move into dark alley
            curr_dt = now.replace(hour=17, minute=45, second=0)
            for lat, lon in ROUTE_POST_EVENT_ALLEY:
                curr_dt += timedelta(minutes=3)
                self.journey_service.add_point(
                    journey_id=journey_id,
                    latitude=lat,
                    longitude=lon,
                    speed_kmh=0.0,
                    stop_duration_sec=480, # 8 min stop
                    timestamp_str=curr_dt.isoformat()
                )

            return {
                "scenario": "post_event_anomaly",
                "title": "Demo 3: Post-Event Prolonged Linger Anomaly",
                "description": "Match ended at 16:00. At 17:45, user lingers in unlit alley. Concern rises -> Safety Check sent.",
                "journey": self.journey_service.get_journey(journey_id)
            }

        elif scenario_name == "timeout_escalate":
            # Scenario 4: Post-event anomaly followed by safety check countdown expiry -> Escalated to guardian
            res = self.run_scenario("post_event_anomaly", user_id)
            j = res["journey"]
            if j.get("active_safety_check"):
                check_id = j["active_safety_check"]["id"]
                SafetyCheckService.handle_timeout(check_id)

            return {
                "scenario": "timeout_escalate",
                "title": "Demo 4: Safety Check Timeout -> Guardian Escalation",
                "description": "Safety check received no user response within 60 seconds. System automatically escalates to guardian.",
                "journey": self.journey_service.get_journey(j["id"])
            }

        elif scenario_name == "explicit_help":
            # Scenario 5: User taps "I Need Help" -> Instant Emergency Escalation
            start_time = now.replace(hour=20, minute=30, second=0).isoformat()
            journey = self.journey_service.start_journey(
                user_id=user_id,
                origin_name="University Campus",
                destination_name="Home",
                custom_start_time=start_time
            )
            journey_id = journey["id"]

            # Add current location point
            self.journey_service.add_point(
                journey_id=journey_id,
                latitude=28.5860,
                longitude=77.2390,
                speed_kmh=0.0,
                stop_duration_sec=120,
                timestamp_str=start_time,
                is_help_requested=True
            )

            # Spawn and trigger emergency help response
            sc = SafetyCheckService.create_safety_check(journey_id, timeout_sec=60, evidence_summary="Explicit help request by user.")
            SafetyCheckService.handle_response(sc["id"], "need_help")

            return {
                "scenario": "explicit_help",
                "title": "Demo 5: Explicit Help Request (Instant Override)",
                "description": "User clicks 'I Need Help'. System overrides ML threshold and escalates immediately.",
                "journey": self.journey_service.get_journey(journey_id)
            }

        elif scenario_name == "false_positive_learn":
            # Scenario 6: User takes unusual route, is asked, confirms "I'm Safe" -> Learns pattern
            res = self.run_scenario("stadium_deviation", user_id)
            j = res["journey"]
            sc = SafetyCheckService.create_safety_check(j["id"], timeout_sec=60, evidence_summary="Unusual deviation check.")
            SafetyCheckService.handle_response(sc["id"], "safe")

            return {
                "scenario": "false_positive_learn",
                "title": "Demo 6: False Positive Avoided & Learned",
                "description": "User confirms 'I'm Safe'. Concern drops to Normal and event is learned as legitimate context.",
                "journey": self.journey_service.get_journey(j["id"])
            }

        return {"error": f"Unknown scenario: {scenario_name}"}

    def inject_custom_anomaly(self, journey_id: int, anomaly_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Injects a dynamic anomaly into an active journey:
        - 'stop': dwell at current point for N minutes
        - 'detour': jump to stadium alley
        - 'clock_advance': advance simulated time past event end
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trajectory_points WHERE journey_id = ? ORDER BY id DESC LIMIT 1", (journey_id,))
        last_pt = cursor.fetchone()
        conn.close()

        lat = last_pt["latitude"] if last_pt else LOC_HOME[0]
        lon = last_pt["longitude"] if last_pt else LOC_HOME[1]
        now_iso = datetime.now(timezone.utc).isoformat()

        if anomaly_type == "stop":
            duration = params.get("duration_sec", 600)
            return self.journey_service.add_point(
                journey_id=journey_id,
                latitude=lat,
                longitude=lon,
                speed_kmh=0.0,
                stop_duration_sec=duration,
                timestamp_str=now_iso
            )
        elif anomaly_type == "detour":
            return self.journey_service.add_point(
                journey_id=journey_id,
                latitude=LOC_STADIUM_ALLEY[0],
                longitude=LOC_STADIUM_ALLEY[1],
                speed_kmh=12.0,
                stop_duration_sec=0,
                timestamp_str=now_iso
            )
        elif anomaly_type == "clock_advance":
            # Jump clock to 18:00
            today = datetime.now()
            jump_ts = today.replace(hour=18, minute=0, second=0).isoformat()
            return self.journey_service.add_point(
                journey_id=journey_id,
                latitude=lat,
                longitude=lon,
                speed_kmh=0.0,
                stop_duration_sec=360,
                timestamp_str=jump_ts
            )
        
        return {"error": "Invalid anomaly type"}
