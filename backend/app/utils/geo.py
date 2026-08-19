"""
Geographical and Spatial Mathematics Utilities for Guardian AI
"""
import math
from typing import List, Tuple, Dict, Any

EARTH_RADIUS_M = 6371000.0  # Earth's radius in meters

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on the earth in meters.
    """
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(d_lon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_M * c

def point_to_segment_distance(
    p_lat: float, p_lon: float,
    a_lat: float, a_lon: float,
    b_lat: float, b_lon: float
) -> float:
    """
    Calculate the minimum distance in meters from point P to line segment AB.
    Uses equirectangular projection approximation for local planar coordinates.
    """
    # Convert lat/lon to approximate planar coordinates in meters relative to point A
    lat_rad = math.radians(a_lat)
    
    # Delta meters from A
    def to_xy(lat: float, lon: float):
        x = math.radians(lon - a_lon) * EARTH_RADIUS_M * math.cos(lat_rad)
        y = math.radians(lat - a_lat) * EARTH_RADIUS_M
        return x, y

    px, py = to_xy(p_lat, p_lon)
    bx, by = to_xy(b_lat, b_lon)

    # Segment length squared
    l2 = bx * bx + by * by
    if l2 == 0.0:
        return haversine_distance(p_lat, p_lon, a_lat, a_lon)

    # Projection factor t clamped between 0 and 1
    t = max(0.0, min(1.0, (px * bx + py * by) / l2))
    
    proj_x = t * bx
    proj_y = t * by

    # Distance from P to projection point
    dx = px - proj_x
    dy = py - proj_y
    return math.sqrt(dx * dx + dy * dy)

def route_deviation(lat: float, lon: float, waypoints: List[Tuple[float, float]]) -> float:
    """
    Calculate minimum distance in meters from (lat, lon) to the polyline formed by waypoints.
    """
    if not waypoints:
        return 0.0
    if len(waypoints) == 1:
        return haversine_distance(lat, lon, waypoints[0][0], waypoints[0][1])

    min_dist = float('inf')
    for i in range(len(waypoints) - 1):
        a_lat, a_lon = waypoints[i]
        b_lat, b_lon = waypoints[i + 1]
        d = point_to_segment_distance(lat, lon, a_lat, a_lon, b_lat, b_lon)
        if d < min_dist:
            min_dist = d

    return min_dist

def route_similarity(actual_trajectory: List[Tuple[float, float]], baseline_waypoints: List[Tuple[float, float]]) -> float:
    """
    Computes a 0 - 100 similarity score between an actual trajectory and baseline route corridor.
    100 = perfectly on corridor, 0 = completely detached.
    """
    if not actual_trajectory or not baseline_waypoints:
        return 100.0

    total_deviation = 0.0
    for p_lat, p_lon in actual_trajectory:
        dev = route_deviation(p_lat, p_lon, baseline_waypoints)
        total_deviation += dev

    avg_deviation = total_deviation / len(actual_trajectory)
    # Deviation of 0m -> 100 similarity; 500m -> ~50; >1000m -> ~0
    similarity = max(0.0, min(100.0, 100.0 - (avg_deviation / 10.0)))
    return round(similarity, 1)

def destination_novelty(dest_lat: float, dest_lon: float, trusted_locations: List[Dict[str, Any]]) -> float:
    """
    Returns 0 - 100 novelty score.
    0 = matches known trusted destination within radius.
    100 = completely unknown / unfamiliar location far away.
    """
    if not trusted_locations:
        return 50.0

    min_dist = float('inf')
    for loc in trusted_locations:
        d = haversine_distance(dest_lat, dest_lon, loc["latitude"], loc["longitude"])
        radius = loc.get("radius_m", 200.0)
        if d <= radius:
            return 0.0  # inside trusted zone
        if d < min_dist:
            min_dist = d

    # 0 at 200m, 50 at 1000m, 100 at 3000m+
    novelty = min(100.0, (min_dist / 30.0))
    return round(novelty, 1)
