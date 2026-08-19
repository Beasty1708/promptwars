"""
Unit Tests for Risk Fusion, Overrides, and Explainability Evidence
"""
from backend.app.services.risk_engine import RiskEngine

def test_risk_fusion_normal_corridor():
    engine = RiskEngine()
    # At normal corridor, 9:15 AM
    traj = [(28.6139, 77.2090), (28.5850, 77.1980)]
    res = engine.evaluate_journey_state(
        user_id=1,
        journey_id=1,
        current_lat=28.5850,
        current_lon=77.1980, # near baseline (77.1980)
        speed_kmh=25.0,
        stop_duration_sec=0,
        timestamp_str="2026-08-19T09:15:00",
        actual_trajectory=traj
    )
    assert res["final_concern"] < 40.0
    assert res["tier"] in ("normal", "monitor")
    assert len(res["evidence"]) > 0

def test_risk_fusion_context_mitigation():
    engine = RiskEngine()
    # At stadium during match time (14:30)
    traj = [(28.6139, 77.2090), (28.5830, 77.2340)]
    res = engine.evaluate_journey_state(
        user_id=1,
        journey_id=1,
        current_lat=28.5830,
        current_lon=77.2340,
        speed_kmh=20.0,
        stop_duration_sec=0,
        timestamp_str="2026-08-19T14:30:00",
        actual_trajectory=traj
    )
    # Personal anomaly is high (deviated to stadium), but context explains it!
    assert res["context_explanation"] >= 70.0
    # Concern is kept under control (not safety check or high concern)
    assert res["tier"] in ("normal", "monitor")

def test_risk_fusion_explicit_help_override():
    engine = RiskEngine()
    res = engine.evaluate_journey_state(
        user_id=1,
        journey_id=1,
        current_lat=28.6139,
        current_lon=77.2090,
        speed_kmh=0.0,
        stop_duration_sec=0,
        timestamp_str="2026-08-19T14:30:00",
        actual_trajectory=[],
        is_help_requested=True
    )
    assert res["final_concern"] == 100.0
    assert res["tier"] == "high_concern"
    assert "emergency" in " ".join(res["evidence"]).lower()
