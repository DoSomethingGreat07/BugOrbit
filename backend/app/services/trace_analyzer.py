from __future__ import annotations

from app.models.schemas import StructuredTrace, TraceAnalysis


class TraceAnalyzerService:
    def analyze(self, trace: StructuredTrace) -> TraceAnalysis:
        failing_span = next(
            (
                span
                for span in trace.raw_spans
                if span.status == "error" or span.error_type
            ),
            None,
        )

        failure_point = failing_span.service if failing_span else trace.root_service
        suspected_issues = self._hypotheses(trace, failure_point)
        summary = (
            f"Trace {trace.trace_id} indicates the primary failure surfaced in "
            f"{failure_point} on {trace.root_endpoint}."
        )
        return TraceAnalysis(
            failure_point=failure_point,
            suspected_issues=suspected_issues,
            summary=summary,
        )

    def _hypotheses(self, trace: StructuredTrace, failure_point: str) -> list[str]:
        hypotheses = [
            f"{failure_point} returned or propagated {trace.error_type or 'an upstream error'}.",
            "A downstream dependency in the span chain likely degraded before the root span failed.",
        ]
        if trace.latency_ms > 2000:
            hypotheses.append("High aggregate latency suggests saturation, retries, or a blocking dependency.")
        critical_alerts = trace.telemetry_summary.get("critical_alerts", [])
        if critical_alerts:
            hypotheses.append(
                f"{len(critical_alerts)} critical alerts were active during the failure window, increasing confidence in infrastructure or dependency instability."
            )
        hot_metrics = trace.telemetry_summary.get("hot_metrics", [])
        if hot_metrics:
            metric_names = ", ".join(metric["name"] for metric in hot_metrics[:3])
            hypotheses.append(
                f"Telemetry anomalies were detected in {metric_names}, which may indicate resource pressure or elevated error budgets."
            )
        incident_hints = trace.telemetry_summary.get("incident_hints", [])
        if incident_hints:
            hypotheses.append(
                f"Contextual hints mention: {', '.join(incident_hints[:3])}, which should be checked against the failing path."
            )
        return hypotheses
