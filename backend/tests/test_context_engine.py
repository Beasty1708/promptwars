"""
Unit Tests for Context Intelligence Engine
"""
from backend.app.services.context_engine import ContextEngine
from backend.app.utils.time_utils import temporal_overlap_score

def test_temporal_overlap_active_event():
    # Current time is 15:00, event is 14:00 - 16:00
    expl, mismatch, reason = temporal_overlap_score("2026-08-19T15:00:00", "2026-08-19T14:00:00", "2026-08-19T16:00:00")
    assert expl >= 80.0
    assert mismatch <= 10.0
    assert "overlaps" in reason.lower()

def test_temporal_overlap_pre_event():
    # Current time is 13:30, event starts at 14:00 (30 mins before)
    expl, mismatch, reason = temporal_overlap_score("2026-08-19T13:30:00", "2026-08-19T14:00:00", "2026-08-19T16:00:00")
    assert expl >= 60.0
    assert "before" in reason.lower()

def test_temporal_overlap_post_event_linger():
    # Current time is 17:45, event concluded at 16:00 (105 mins linger)
    expl, mismatch, reason = temporal_overlap_score("2026-08-19T17:45:00", "2026-08-19T14:00:00", "2026-08-19T16:00:00")
    assert expl <= 20.0
    assert mismatch >= 70.0
    assert "prolonged" in reason.lower() or "concluded" in reason.lower()

def test_context_engine_stadium_query():
    engine = ContextEngine()
    # Query at Stadium (28.5830, 77.2340) during match time
    ctx = engine.evaluate_context(28.5830, 77.2340, "2026-08-19T15:00:00")
    assert ctx["has_context"] is True
    assert ctx["explanation_score"] >= 70.0
    assert "football" in ctx["matched_event"]["title"].lower() or "sports" in ctx["matched_event"]["category"].lower()
