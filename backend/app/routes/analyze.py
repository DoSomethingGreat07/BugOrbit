from typing import Any

from fastapi import APIRouter

from app.models.schemas import FinalAnalysisResponse
from app.services.orchestrator import RocketRideOrchestrator
from app.services.telemetry_normalizer import TelemetryNormalizationService


router = APIRouter()
orchestrator = RocketRideOrchestrator()
normalizer = TelemetryNormalizationService()


@router.post("", response_model=FinalAnalysisResponse)
async def analyze_trace(payload: dict[str, Any]) -> FinalAnalysisResponse:
    request = normalizer.normalize_payload(payload)
    return orchestrator.run(request)
