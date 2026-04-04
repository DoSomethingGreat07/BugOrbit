from __future__ import annotations

from app.db.neo4j import Neo4jService
from app.models.schemas import FinalAnalysisResponse, TraceIngestRequest
from app.services.graph_query import GraphQueryService
from app.services.impact_analyzer import ImpactAnalyzerService
from app.services.incident_state import incident_state_service
from app.services.narrative_builder import NarrativeBuilderService
from app.services.rag_service import RAGIncidentResolver
from app.services.trace_analyzer import TraceAnalyzerService
from app.services.trace_ingestion import TraceIngestionService


class RocketRideOrchestrator:
    def __init__(self) -> None:
        self.trace_ingestion = TraceIngestionService()
        self.trace_analyzer = TraceAnalyzerService()
        self.graph_query = GraphQueryService()
        self.neo4j = Neo4jService()
        self.impact_analyzer = ImpactAnalyzerService()
        self.rag_resolver = RAGIncidentResolver()
        self.narrative_builder = NarrativeBuilderService()

    def run(self, request: TraceIngestRequest) -> FinalAnalysisResponse:
        structured_trace = self.trace_ingestion.parse_trace(request)
        trace_analysis = self.trace_analyzer.analyze(structured_trace)
        self.neo4j.sync_trace_graph(request, structured_trace, trace_analysis)
        cypher = self.graph_query.generate_cypher(trace_analysis.failure_point)
        graph_result = self.neo4j.query_impacted_services(trace_analysis.failure_point, cypher)
        impact_analysis = self.impact_analyzer.analyze(structured_trace, graph_result)
        incident_query = " ".join(
            [
                trace_analysis.failure_point,
                structured_trace.error_type or "",
                structured_trace.root_endpoint,
            ]
        ).strip()
        incident_matches = self.rag_resolver.search(incident_query)
        root_cause, solutions, confidence = self.rag_resolver.synthesize(
            structured_trace,
            trace_analysis,
            graph_result,
            impact_analysis,
            incident_matches,
        )
        narrative = self.narrative_builder.build(
            structured_trace,
            trace_analysis,
            graph_result,
            impact_analysis,
            incident_matches,
            root_cause,
            solutions,
        )
        self.neo4j.sync_analysis_graph(
            structured_trace,
            trace_analysis,
            graph_result,
            impact_analysis,
            incident_matches,
            root_cause,
            confidence,
            solutions,
        )

        response = FinalAnalysisResponse(
            structured_trace=structured_trace,
            trace_analysis=trace_analysis,
            graph_result=graph_result,
            impact_analysis=impact_analysis,
            incident_matches=incident_matches,
            root_cause=root_cause,
            solutions=solutions,
            confidence_score=confidence,
            narrative=narrative,
        )
        incident_state_service.upsert_analysis(request, response)
        return response
