from __future__ import annotations

from pathlib import Path
import re

from app.core.config import settings
from app.db.neo4j import Neo4jService
from app.db.vector_db import IncidentVectorStore
from app.models.schemas import (
    GraphFixHistoryRecord,
    GraphQueryResult,
    ImpactAnalysis,
    IncidentRecord,
    RecommendationItem,
    StructuredTrace,
    TraceAnalysis,
)
from app.services.llm_reasoner import OpenAIReasoningService


class RAGIncidentResolver:
    def __init__(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        self.store = IncidentVectorStore(repo_root / "data/incidents/sample_incidents.json")
        self.reasoner = OpenAIReasoningService()
        self.neo4j = Neo4jService()

    def search(self, query: str) -> list[IncidentRecord]:
        return self.store.search(query, top_k=settings.vector_top_k)

    def synthesize(
        self,
        structured_trace: StructuredTrace,
        trace_analysis: TraceAnalysis,
        graph_result: GraphQueryResult,
        impact_analysis: ImpactAnalysis,
        incidents: list[IncidentRecord],
    ) -> tuple[str, list[str], list[RecommendationItem], float]:
        graph_fix_history = self._graph_fix_history(structured_trace, trace_analysis, graph_result, impact_analysis)
        llm_result = self.reasoner.synthesize_incident_response(
            structured_trace,
            trace_analysis,
            graph_result,
            impact_analysis,
            incidents,
            graph_fix_history,
        )
        graph_solutions = self._rank_graph_fix_actions(graph_fix_history)
        if llm_result:
            root_cause, solutions, confidence = llm_result
            merged_solutions = self._merge_solutions(solutions, graph_solutions)
            return (
                root_cause,
                merged_solutions,
                self._tag_recommendations(merged_solutions, incidents, graph_fix_history),
                confidence,
            )

        if not incidents:
            solutions = graph_solutions or ["Inspect the failing service logs and dependency health metrics."]
            return (
                "No closely matching incident was found. Root cause remains provisional.",
                solutions,
                self._tag_recommendations(solutions, incidents, graph_fix_history),
                0.45 if graph_solutions else 0.35,
            )

        primary = incidents[0]
        confidence = min(0.95, 0.45 + (0.15 * len(incidents)) + (0.05 if graph_solutions else 0))
        solutions = self._merge_solutions(primary.fix, graph_solutions)
        return primary.root_cause, solutions, self._tag_recommendations(solutions, incidents, graph_fix_history), confidence

    def _graph_fix_history(
        self,
        structured_trace: StructuredTrace,
        trace_analysis: TraceAnalysis,
        graph_result: GraphQueryResult,
        impact_analysis: ImpactAnalysis,
    ) -> list[GraphFixHistoryRecord]:
        services = [
            trace_analysis.failure_point,
            structured_trace.root_service,
            *graph_result.affected_services,
            *impact_analysis.blast_radius,
        ]
        return self.neo4j.query_fix_history(services=services, error_type=structured_trace.error_type, limit=6)

    def _rank_graph_fix_actions(self, records: list[GraphFixHistoryRecord]) -> list[str]:
        if not records:
            return []

        scored: dict[str, float] = {}
        for index, record in enumerate(records):
            base = max(1.0, 6 - index)
            if record.feedback == "Resolved":
                base += 3.0
            elif record.feedback == "Improved":
                base += 1.5
            if record.result == "success":
                base += 2.0
            if record.status == "resolved":
                base += 1.5
            if record.final_resolution:
                base += 1.0
            scored[record.fix_action] = scored.get(record.fix_action, 0.0) + base

        return [action for action, _score in sorted(scored.items(), key=lambda item: (-item[1], item[0]))[:4]]

    def _merge_solutions(self, incident_fixes: list[str], graph_fixes: list[str]) -> list[str]:
        merged: list[str] = []
        for item in [*graph_fixes, *incident_fixes]:
            if item and item not in merged:
                merged.append(item)
        return merged[:5]

    def _tag_recommendations(
        self,
        solutions: list[str],
        incidents: list[IncidentRecord],
        graph_fix_history: list[GraphFixHistoryRecord],
    ) -> list[RecommendationItem]:
        tagged: list[RecommendationItem] = []
        for solution in solutions:
            graph_match = next((record for record in graph_fix_history if self._same_fix(record.fix_action, solution)), None)
            if graph_match:
                tagged.append(
                    RecommendationItem(
                        text=solution,
                        source="graph_history",
                        evidence_incident_id=graph_match.incident_id,
                    )
                )
                continue

            incident_match = next(
                (
                    incident
                    for incident in incidents
                    if any(self._same_fix(fix, solution) for fix in incident.fix)
                ),
                None,
            )
            if incident_match:
                tagged.append(
                    RecommendationItem(
                        text=solution,
                        source="incident_memory",
                        evidence_incident_id=incident_match.incident_id,
                    )
                )
                continue

            tagged.append(RecommendationItem(text=solution, source="llm"))
        return tagged

    def _same_fix(self, left: str, right: str) -> bool:
        left_norm = self._normalize_fix_text(left)
        right_norm = self._normalize_fix_text(right)
        if not left_norm or not right_norm:
            return False
        if left_norm == right_norm:
            return True
        if left_norm in right_norm or right_norm in left_norm:
            return True

        left_tokens = set(left_norm.split())
        right_tokens = set(right_norm.split())
        overlap = left_tokens & right_tokens
        if not overlap:
            return False
        return len(overlap) / max(1, min(len(left_tokens), len(right_tokens))) >= 0.6

    def _normalize_fix_text(self, text: str) -> str:
        lowered = text.strip().lower()
        lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
        lowered = re.sub(r"\s+", " ", lowered).strip()
        synonym_map = {
            "database": "db",
            "connection": "pool",
            "capacity": "size",
            "increase": "raise",
            "expand": "raise",
        }
        tokens = [synonym_map.get(token, token) for token in lowered.split()]
        stopwords = {"the", "a", "an", "for", "to", "and", "of", "in", "service"}
        return " ".join(token for token in tokens if token not in stopwords)
