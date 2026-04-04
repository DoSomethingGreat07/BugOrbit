from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.db.vector_db import IncidentVectorStore
from app.models.schemas import GraphQueryResult, ImpactAnalysis, IncidentRecord, StructuredTrace, TraceAnalysis
from app.services.llm_reasoner import OpenAIReasoningService


class RAGIncidentResolver:
    def __init__(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        self.store = IncidentVectorStore(repo_root / "data/incidents/sample_incidents.json")
        self.reasoner = OpenAIReasoningService()

    def search(self, query: str) -> list[IncidentRecord]:
        return self.store.search(query, top_k=settings.vector_top_k)

    def synthesize(
        self,
        structured_trace: StructuredTrace,
        trace_analysis: TraceAnalysis,
        graph_result: GraphQueryResult,
        impact_analysis: ImpactAnalysis,
        incidents: list[IncidentRecord],
    ) -> tuple[str, list[str], float]:
        llm_result = self.reasoner.synthesize_incident_response(
            structured_trace,
            trace_analysis,
            graph_result,
            impact_analysis,
            incidents,
        )
        if llm_result:
            return llm_result

        if not incidents:
            return (
                "No closely matching incident was found. Root cause remains provisional.",
                ["Inspect the failing service logs and dependency health metrics."],
                0.35,
            )

        primary = incidents[0]
        confidence = min(0.95, 0.45 + (0.15 * len(incidents)))
        return primary.root_cause, primary.fix, confidence
