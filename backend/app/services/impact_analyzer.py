from __future__ import annotations

from app.models.schemas import GraphQueryResult, ImpactAnalysis, StructuredTrace


class ImpactAnalyzerService:
    def analyze(self, trace: StructuredTrace, graph_result: GraphQueryResult) -> ImpactAnalysis:
        blast_radius = [trace.root_service, *graph_result.affected_services]
        critical_paths = []
        if graph_result.affected_services:
            critical_paths.append([trace.root_service, graph_result.affected_services[0]])
        severity = "high" if trace.error_type or len(blast_radius) >= 3 else "medium"
        return ImpactAnalysis(
            blast_radius=list(dict.fromkeys(blast_radius)),
            critical_paths=critical_paths,
            severity=severity,
        )
