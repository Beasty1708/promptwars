"""
Pydantic Data Validation and Serialization Schemas for Guardian AI
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# --- User & Profile ---
class UserBase(BaseModel):
    name: str
    phone_masked: str
    monitoring_enabled: bool = True

class UserResponse(UserBase):
    id: int
    created_at: str

# --- Trusted Locations ---
class TrustedLocationBase(BaseModel):
    name: str
    type: str # home, university, work, gym, other
    latitude: float
    longitude: float
    radius_m: float = 200.0

class TrustedLocationCreate(TrustedLocationBase):
    user_id: int

class TrustedLocationResponse(TrustedLocationBase):
    id: int
    user_id: int
    created_at: str

# --- Guardians ---
class GuardianBase(BaseModel):
    name: str
    relationship: str
    contact_masked: str
    priority: int = 1 # 1 = primary, 2 = secondary
    enabled: bool = True

class GuardianCreate(GuardianBase):
    user_id: int

class GuardianResponse(GuardianBase):
    id: int
    user_id: int

# --- Trajectory Points ---
class TrajectoryPointCreate(BaseModel):
    timestamp: Optional[str] = None
    latitude: float
    longitude: float
    speed_kmh: float = 25.0
    heading: float = 0.0
    stop_duration_sec: int = 0

class TrajectoryPointResponse(TrajectoryPointCreate):
    id: int
    journey_id: int

# --- Risk & Explainability ---
class RiskBreakdown(BaseModel):
    personal_anomaly: float
    environmental_risk: float
    context_explanation: float
    context_mismatch: float
    final_concern: float
    tier: str # normal, monitor, safety_check, high_concern
    evidence: List[str]
    details: Dict[str, Any] = {}

# --- Journeys ---
class JourneyStartRequest(BaseModel):
    user_id: int
    origin_name: str = "Home"
    destination_name: str = "University Campus"
    expected_duration_sec: int = 1800
    custom_start_time: Optional[str] = None

class JourneyResponse(BaseModel):
    id: int
    user_id: int
    origin_name: str
    destination_name: str
    started_at: str
    finished_at: Optional[str]
    expected_duration_sec: int
    actual_duration_sec: int
    status: str
    anomaly_score: float
    environmental_score: float
    context_score: float
    final_concern_score: float
    tier: str

# --- Context Events ---
class ContextEventResponse(BaseModel):
    id: int
    title: str
    category: str
    venue: str
    latitude: float
    longitude: float
    radius_m: float
    start_at: str
    end_at: str
    confidence: float

# --- Safety Checks ---
class SafetyCheckResponse(BaseModel):
    id: int
    journey_id: int
    sent_at: str
    timeout_sec: int
    response: Optional[str]
    responded_at: Optional[str]
    status: str
    evidence_summary: Optional[str]

class SafetyCheckAction(BaseModel):
    response: str # safe, need_help, cant_talk

# --- Alerts & Guardian View ---
class AlertResponse(BaseModel):
    id: int
    journey_id: int
    alert_type: str
    severity: str
    message: str
    evidence: List[str]
    created_at: str
    status: str
    user_name: Optional[str] = None
    last_location: Optional[Dict[str, float]] = None

class AlertAction(BaseModel):
    action: str # acknowledge, resolve

# --- Simulation Controls ---
class SimulationStartRequest(BaseModel):
    scenario: str # normal, stadium_deviation, post_event_anomaly, timeout_escalate, explicit_help, false_positive_learn
    user_id: int = 1

class SimulationInjectRequest(BaseModel):
    journey_id: int
    anomaly_type: str # route_deviation, stop, speed_drop, jump_to_stadium, clock_advance
    params: Dict[str, Any] = {}

class SimulationAdvanceRequest(BaseModel):
    journey_id: int
    step_index: Optional[int] = None
