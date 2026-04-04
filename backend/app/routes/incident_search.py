from fastapi import APIRouter, HTTPException

from app.models.schemas import IncidentFixRequest, IncidentSearchResponse, IncidentStateResponse
from app.services.incident_state import incident_state_service
from app.services.rag_service import RAGIncidentResolver


router = APIRouter()
resolver = RAGIncidentResolver()


@router.post("/search", response_model=IncidentSearchResponse)
async def search_incidents(query: str) -> IncidentSearchResponse:
    matches = resolver.search(query)
    return IncidentSearchResponse(query=query, matches=matches)


@router.get("/state", response_model=IncidentStateResponse)
async def incident_state_snapshot() -> IncidentStateResponse:
    return incident_state_service.state()


@router.post("/fix", response_model=IncidentStateResponse)
async def record_fix(request: IncidentFixRequest) -> IncidentStateResponse:
    try:
        return incident_state_service.record_fix(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Incident {request.incident_id} not found") from exc
