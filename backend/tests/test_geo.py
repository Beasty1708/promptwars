"""
Unit Tests for Geo and Spatial Utilities
"""
import pytest
from backend.app.utils.geo import (
    haversine_distance,
    point_to_segment_distance,
    route_deviation,
    route_similarity,
    destination_novelty
)

def test_haversine_distance_known_points():
    # Delhi Home to University Campus approx ~8-9 km
    d = haversine_distance(28.6139, 77.2090, 28.5450, 77.1926)
    assert 7500 < d < 9000

def test_haversine_same_point():
    d = haversine_distance(28.6139, 77.2090, 28.6139, 77.2090)
    assert d == pytest.approx(0.0, abs=0.01)

def test_point_to_segment():
    # Line from (28.60, 77.20) to (28.50, 77.20) (north-south)
    # Point at (28.55, 77.20) is on line -> distance ~ 0
    d = point_to_segment_distance(28.55, 77.20, 28.60, 77.20, 28.50, 77.20)
    assert d < 10.0

def test_route_deviation_and_similarity():
    corridor = [
        (28.6139, 77.2090),
        (28.5850, 77.2000),
        (28.5450, 77.1926)
    ]
    # Point right on corridor
    dev_on = route_deviation(28.5850, 77.2000, corridor)
    assert dev_on < 10.0

    # Point far off corridor (e.g. at Stadium 28.5830, 77.2340 ~ 3.5 km east)
    dev_off = route_deviation(28.5830, 77.2340, corridor)
    assert dev_off > 2000.0

    # Route similarity test
    sim_perfect = route_similarity([(28.6139, 77.2090), (28.5850, 77.2000)], corridor)
    assert sim_perfect > 95.0

    sim_bad = route_similarity([(28.5830, 77.2340), (28.5860, 77.2390)], corridor)
    assert sim_bad < 30.0

def test_destination_novelty():
    trusted = [
        {"name": "Home", "latitude": 28.6139, "longitude": 77.2090, "radius_m": 250.0},
        {"name": "University", "latitude": 28.5450, "longitude": 77.1926, "radius_m": 300.0}
    ]
    # Point at Home -> novelty 0
    assert destination_novelty(28.6139, 77.2090, trusted) == 0.0
    # Unknown point far away -> high novelty
    assert destination_novelty(28.7500, 77.3500, trusted) > 80.0
