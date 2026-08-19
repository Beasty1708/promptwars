"""
Journey Lifecycle, GPS Points, and Timeline API Router
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from ..schemas import JourneyStartRequest, TrajectoryPointCreate, JourneyResponse, RiskBreakdown
from ..services.journey_service import JourneyService
from ..services.risk_engine import RiskEngine

router = APIRouter(prefix="/api/journeys", tags=["Journeys"])
journey_service = JourneyService()
risk_engine = RiskEngine()

@router.post("/start", response_model=Dict[str, Any])
def start_journey(payload: JourneyStartRequest):
    return journey_service.start_journey(
        user_id=payload.user_id,
        origin_name=payload.origin_name,
        destination_name=payload.destination_name,
        expected_duration_sec=payload.expected_duration_sec,
        custom_start_time=payload.custom_start_time
    )

@router.get("/{journey_id}", response_model=Dict[str, Any])
def get_journey(journey_id: int):
    j = journey_service.get_journey(journey_id)
    if not j:
        raise HTTPException(status_code=404, detail="Journey not found")
    return j

@router.post("/{journey_id}/point", response_model=Dict[str, Any])
def add_journey_point(journey_id: int, payload: TrajectoryPointCreate):
    res = journey_service.add_point(
        journey_id=journey_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        speed_kmh=payload.speed_kmh,
        heading=payload.heading,
        stop_duration_sec=payload.stop_duration_sec,
        timestamp_str=payload.timestamp
    )
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.post("/{journey_id}/finish", response_model=Dict[str, Any])
def finish_journey(journey_id: int):
    return journey_service.finish_journey(journey_id)

@router.get("/{journey_id}/risk")
def get_journey_risk(journey_id: int):
    j = journey_service.get_journey(journey_id)
    if not j or not j.get("trajectory"):
        raise HTTPException(status_code=404, detail="Journey or trajectory not found")
    
    last_pt = j["trajectory"][-1]
    traj = [(p["latitude"], p["longitude"]) for p in j["trajectory"]]
    
    return risk_engine.evaluate_journey_state(
        user_id=j["user_id"],
        journey_id=journey_id,
        current_lat=last_pt["latitude"],
        current_lon=last_pt["longitude"],
        speed_kmh=last_pt["speed_kmh"],
        stop_duration_sec=last_pt["stop_duration_sec"],
        timestamp_str=last_pt["timestamp"],
        actual_trajectory=traj
    )
