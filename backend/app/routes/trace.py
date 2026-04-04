from typing import Any

from fastapi import APIRouter

from app.models.schemas import StructuredTrace
from app.services.telemetry_normalizer import TelemetryNormalizationService
from app.services.trace_ingestion import TraceIngestionService


router = APIRouter()
service = TraceIngestionService()
normalizer = TelemetryNormalizationService()


@router.post("", response_model=StructuredTrace)
async def ingest_trace(payload: dict[str, Any]) -> StructuredTrace:
    request = normalizer.normalize_payload(payload)
    return service.parse_trace(request)
