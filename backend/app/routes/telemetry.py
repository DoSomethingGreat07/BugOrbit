from fastapi import APIRouter

from app.models.schemas import FinalAnalysisResponse, LiveTelemetryRequest, StructuredTrace
from app.services.live_telemetry import LiveTelemetryAdapterService
from app.services.orchestrator import RocketRideOrchestrator
from app.services.trace_ingestion import TraceIngestionService


router = APIRouter()
adapter = LiveTelemetryAdapterService()
trace_ingestion = TraceIngestionService()
orchestrator = RocketRideOrchestrator()


@router.post("/normalize", response_model=StructuredTrace)
async def normalize_live_telemetry(request: LiveTelemetryRequest) -> StructuredTrace:
    normalized_request = adapter.normalize(request)
    return trace_ingestion.parse_trace(normalized_request)


@router.post("/analyze", response_model=FinalAnalysisResponse)
async def analyze_live_telemetry(request: LiveTelemetryRequest) -> FinalAnalysisResponse:
    normalized_request = adapter.normalize(request)
    return orchestrator.run(normalized_request)
