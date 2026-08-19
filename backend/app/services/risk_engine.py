"""
Risk Fusion and Explainability Engine for Guardian AI
Fuses Personal Anomaly, Environmental Risk, and Context Intelligence into an interpretable concern score.
"""
from typing import Dict, Any, List
from .environment_service import EnvironmentService
from .context_engine import ContextEngine
from .anomaly_engine import PersonalAnomalyEngine

class RiskEngine:
    def __init__(self):
        self.anomaly_engine = PersonalAnomalyEngine()
        self.context_engine = ContextEngine()
        self.env_service = EnvironmentService()

        # Configurable fusion weights (PRD Section 6)
        self.w_personal = 0.45
        self.w_env = 0.30
        self.w_context = 0.25

        # Configurable thresholds
        self.threshold_normal = 35.0
        self.threshold_monitor = 60.0
        self.threshold_safety_check = 80.0

    def evaluate_journey_state(
        self,
        user_id: int,
        journey_id: int,
        current_lat: float,
        current_lon: float,
        speed_kmh: float,
        stop_duration_sec: int,
        timestamp_str: str,
        actual_trajectory: List[Any],
        is_safe_confirmed: bool = False,
        is_help_requested: bool = False
    ) -> Dict[str, Any]:
        """
        Computes composite concern score and explainability breakdown.
        """
        # Critical override: Explicit Help Request
        if is_help_requested:
            return {
                "personal_anomaly": 95.0,
                "environmental_risk": 75.0,
                "context_explanation": 0.0,
                "context_mismatch": 100.0,
                "final_concern": 100.0,
                "tier": "high_concern",
                "evidence": [
                    "User explicitly requested immediate emergency assistance.",
                    "Emergency escalation triggered instantly."
                ],
                "details": {
                    "is_help_requested": True,
                    "is_safe_confirmed": False
                }
            }

        # 1. Personal Anomaly
        personal = self.anomaly_engine.evaluate_point(
            user_id, journey_id, current_lat, current_lon, speed_kmh,
            stop_duration_sec, timestamp_str, actual_trajectory
        )

        # 2. Environmental Risk
        env = self.env_service.get_environmental_risk(current_lat, current_lon)

        # 3. Context Reasoning
        context = self.context_engine.evaluate_context(current_lat, current_lon, timestamp_str)

        # Calculate Context Mismatch
        context_mismatch = context["mismatch_score"]
        
        # If strong contextual explanation exists, mitigate personal route anomaly (Explain before Escalate)
        adjusted_personal = personal["score"]
        if context["explanation_score"] >= 60.0:
            # Match/event legitimizes the deviation: reduce personal anomaly impact
            mitigation_factor = (context["explanation_score"] / 100.0) * 0.65
            adjusted_personal = personal["score"] * (1.0 - mitigation_factor)

        # Weighted Concern Fusion (PRD Section 6)
        raw_concern = (
            self.w_personal * adjusted_personal +
            self.w_env * env["score"] +
            self.w_context * context_mismatch
        )

        # False positive suppression / Cooldown if user previously confirmed safe
        if is_safe_confirmed:
            raw_concern = raw_concern * 0.35

        final_concern = max(0.0, min(100.0, raw_concern))

        # Determine Tier
        if final_concern < self.threshold_normal:
            tier = "normal"
        elif final_concern < self.threshold_monitor:
            tier = "monitor"
        elif final_concern < self.threshold_safety_check:
            tier = "safety_check"
        else:
            tier = "high_concern"

        # Assemble unified natural-language evidence bullets (PRD Section 30)
        evidence = []
        
        # Add personal evidence
        for ev in personal["evidence"]:
            evidence.append(ev)

        # Add context evidence
        for ev in context["evidence"]:
            evidence.append(ev)

        # Add environmental evidence (selective)
        for ev in env["evidence"][:2]:
            evidence.append(ev)

        if not evidence:
            evidence.append("Journey aligns with normal baseline corridors and safe environmental parameters.")

        return {
            "personal_anomaly": round(personal["score"], 1),
            "environmental_risk": round(env["score"], 1),
            "context_explanation": round(context["explanation_score"], 1),
            "context_mismatch": round(context_mismatch, 1),
            "final_concern": round(final_concern, 1),
            "tier": tier,
            "evidence": evidence,
            "details": {
                "route_deviation_m": personal.get("route_deviation_m", 0.0),
                "route_similarity": personal.get("route_similarity", 100.0),
                "stop_duration_sec": stop_duration_sec,
                "lighting_score": env.get("lighting_score", 70.0),
                "footfall_score": env.get("footfall_score", 60.0),
                "cctv_score": env.get("cctv_score", 50.0),
                "police_distance_km": env.get("police_distance_km", 2.0),
                "matched_event": context.get("matched_event"),
                "is_safe_confirmed": is_safe_confirmed,
                "is_help_requested": is_help_requested
            }
        }
