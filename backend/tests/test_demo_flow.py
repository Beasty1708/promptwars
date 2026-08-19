"""
Integration Tests for Complete PRD Demo Flows
"""
from backend.app.services.simulation_service import SimulationService
from backend.app.services.safety_check_service import SafetyCheckService
from backend.app.services.escalation_service import EscalationService
from backend.app.db import get_db_connection

def test_demo_1_normal_commute():
    sim = SimulationService()
    res = sim.run_scenario("normal", user_id=1)
    j = res["journey"]
    assert j is not None
    assert j["status"] in ("IN_PROGRESS", "COMPLETED")
    assert j["tier"] in ("normal", "monitor")
    assert j["final_concern_score"] < 40.0
    assert j["active_safety_check"] is None

def test_demo_2_stadium_deviation_explained():
    sim = SimulationService()
    res = sim.run_scenario("stadium_deviation", user_id=1)
    j = res["journey"]
    assert j is not None
    # Route was deviated, but football match explains it!
    assert j["context_score"] >= 60.0
    assert j["tier"] in ("normal", "monitor")
    assert j["active_safety_check"] is None

def test_demo_3_post_event_prolonged_stay_triggers_safety_check():
    sim = SimulationService()
    res = sim.run_scenario("post_event_anomaly", user_id=1)
    j = res["journey"]
    assert j is not None
    assert j["status"] == "SAFETY_CHECK"
    assert j["active_safety_check"] is not None
    assert j["active_safety_check"]["status"] == "PENDING"
    assert j["final_concern_score"] >= 60.0

def test_demo_4_timeout_causes_guardian_escalation():
    sim = SimulationService()
    res = sim.run_scenario("timeout_escalate", user_id=1)
    j = res["journey"]
    assert j is not None
    assert j["status"] == "ESCALATED"
    assert j["tier"] == "high_concern"
    
    # Check that alert was created
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alerts WHERE journey_id = ?", (j["id"],))
    alerts = cursor.fetchall()
    assert len(alerts) >= 1
    
    # Check escalation events
    cursor.execute("SELECT * FROM escalation_events WHERE alert_id = ?", (alerts[0]["id"],))
    esc = cursor.fetchall()
    assert len(esc) >= 1
    conn.close()

def test_demo_5_explicit_help_immediate_escalation():
    sim = SimulationService()
    res = sim.run_scenario("explicit_help", user_id=1)
    j = res["journey"]
    assert j["status"] == "ESCALATED"
    assert j["final_concern_score"] == 100.0

def test_demo_6_false_positive_learning_resolution():
    sim = SimulationService()
    res = sim.run_scenario("false_positive_learn", user_id=1)
    j = res["journey"]
    assert j["status"] == "RESOLVED"
    assert j["final_concern_score"] <= 35.0
