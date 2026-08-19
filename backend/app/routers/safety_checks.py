"""
Safety Check Verification and Response API Router
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from ..schemas import SafetyCheckAction
from ..services.safety_check_service import SafetyCheckService

router = APIRouter(prefix="/api/safety-checks", tags=["Safety Checks"])

@router.post("/{check_id}/respond")
def respond_to_safety_check(check_id: int, payload: SafetyCheckAction):
    res = SafetyCheckService.handle_response(check_id, payload.response)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.post("/{check_id}/timeout")
def trigger_safety_check_timeout(check_id: int):
    res = SafetyCheckService.handle_timeout(check_id)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res
