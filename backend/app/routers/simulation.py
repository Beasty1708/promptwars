"""
Interactive Journey Simulation and Demo API Router
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from ..schemas import SimulationStartRequest, SimulationInjectRequest
from ..services.simulation_service import SimulationService

router = APIRouter(prefix="/api/simulation", tags=["Simulation"])
sim_service = SimulationService()

@router.post("/start")
def start_scenario(payload: SimulationStartRequest):
    res = sim_service.run_scenario(payload.scenario, payload.user_id)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.post("/inject-anomaly")
def inject_anomaly(payload: SimulationInjectRequest):
    res = sim_service.inject_custom_anomaly(payload.journey_id, payload.anomaly_type, payload.params)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res
