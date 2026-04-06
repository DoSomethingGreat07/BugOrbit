from __future__ import annotations

from app.models.schemas import (
    AnalysisNarrative,
    GraphQueryResult,
    ImpactAnalysis,
    IncidentRecord,
    RecommendationItem,
    ServiceImpact,
    StructuredTrace,
    TraceAnalysis,
)


class NarrativeBuilderService:
    def build(
        self,
        structured_trace: StructuredTrace,
        trace_analysis: TraceAnalysis,
        graph_result: GraphQueryResult,
        impact_analysis: ImpactAnalysis,
        incident_matches: list[IncidentRecord],
        root_cause: str,
        solutions: list[str],
        recommendation_details: list[RecommendationItem],
    ) -> AnalysisNarrative:
        impacted = impact_analysis.blast_radius or [structured_trace.root_service]
        executive_summary = (
            f"RocketRide analyzed trace {structured_trace.trace_id} and found that "
            f"{trace_analysis.failure_point} is the most likely failure point for "
            f"{structured_trace.root_endpoint}. The strongest current explanation is: "
            f"{root_cause}"
        )

        if len(impacted) == 1:
            affected_services_overview = (
                f"The incident currently appears concentrated in {impacted[0]} with limited downstream spread."
            )
        else:
            affected_services_overview = (
                f"The incident is affecting {', '.join(impacted[:-1])} and {impacted[-1]}. "
                f"Blast radius is currently assessed as {impact_analysis.severity}."
            )

        likely_cause_chain = [
            f"User-facing traffic enters through {structured_trace.root_service} on {structured_trace.root_endpoint}.",
            f"RocketRide detected the first meaningful failure signal in {trace_analysis.failure_point}.",
        ]
        if structured_trace.error_type:
            likely_cause_chain.append(
                f"The dominant error type observed in the trace is {structured_trace.error_type}."
            )
        if graph_result.affected_services:
            likely_cause_chain.append(
                f"Dependency analysis suggests likely downstream propagation through {', '.join(graph_result.affected_services)}."
            )
        if incident_matches:
            likely_cause_chain.append(
                f"Historical incident match {incident_matches[0].incident_id} supports a similar failure pattern."
            )

        service_impacts = self._build_service_impacts(
            structured_trace,
            trace_analysis,
            graph_result,
            impact_analysis,
        )

        recommended_actions = list(dict.fromkeys(solutions))
        return AnalysisNarrative(
            executive_summary=executive_summary,
            affected_services_overview=affected_services_overview,
            likely_cause_chain=likely_cause_chain,
            service_impacts=service_impacts,
            recommended_actions=recommended_actions,
            recommendation_details=recommendation_details,
        )

    def _build_service_impacts(
        self,
        structured_trace: StructuredTrace,
        trace_analysis: TraceAnalysis,
        graph_result: GraphQueryResult,
        impact_analysis: ImpactAnalysis,
    ) -> list[ServiceImpact]:
        hot_metrics = structured_trace.telemetry_summary.get("hot_metrics", [])
        critical_alerts = structured_trace.telemetry_summary.get("critical_alerts", [])
        impacts: list[ServiceImpact] = []

        for service in impact_analysis.blast_radius:
            evidence: list[str] = []
            if service == trace_analysis.failure_point:
                evidence.append("Primary failure point detected in trace analysis.")
            service_metrics = [m["name"] for m in hot_metrics if m.get("service") == service][:2]
            if service_metrics:
                evidence.append(f"Hot metrics: {', '.join(service_metrics)}.")
            service_alerts = [a["name"] for a in critical_alerts if a.get("service") == service][:2]
            if service_alerts:
                evidence.append(f"Alerts: {', '.join(service_alerts)}.")
            if service in graph_result.affected_services:
                evidence.append("Dependency graph marks this service as part of the propagation path.")
            impact = self._impact_sentence(service, structured_trace, trace_analysis, graph_result)
            impacts.append(ServiceImpact(service=service, impact=impact, evidence=evidence))

        return impacts

    def _impact_sentence(
        self,
        service: str,
        structured_trace: StructuredTrace,
        trace_analysis: TraceAnalysis,
        graph_result: GraphQueryResult,
    ) -> str:
        if service == structured_trace.root_service:
            return (
                f"{service} is the customer-facing entry point and is likely surfacing elevated latency or timeout symptoms."
            )
        if service == trace_analysis.failure_point:
            return (
                f"{service} is the most likely service causing the incident based on error propagation and trace failure signals."
            )
        if service in graph_result.affected_services:
            return (
                f"{service} is likely affected through dependency propagation and may contribute to spread or user-visible degradation."
            )
        return f"{service} appears in the observed telemetry and should be monitored for secondary impact."
