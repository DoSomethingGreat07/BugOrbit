from __future__ import annotations

from app.models.schemas import Span, StructuredTrace, TraceIngestRequest


class TraceIngestionService:
    def parse_trace(self, request: TraceIngestRequest) -> StructuredTrace:
        root_span = self._find_root_span(request.spans)
        latency_ms = sum(span.duration_ms for span in request.spans)
        error_span = next((span for span in request.spans if span.error_type or span.status == "error"), None)

        call_graph = [
            {
                "span_id": span.span_id,
                "parent_id": span.parent_id,
                "service": span.service,
                "operation": span.operation,
                "status": span.status,
                "duration_ms": span.duration_ms,
            }
            for span in request.spans
        ]

        return StructuredTrace(
            trace_id=request.trace_id,
            provider=request.provider,
            root_service=root_span.service,
            root_endpoint=root_span.operation,
            error_type=error_span.error_type if error_span else None,
            latency_ms=latency_ms,
            call_graph=call_graph,
            raw_spans=request.spans,
            telemetry_summary=self._build_telemetry_summary(request),
        )

    def _find_root_span(self, spans: list[Span]) -> Span:
        root = next((span for span in spans if not span.parent_id), None)
        return root or spans[0]

    def _build_telemetry_summary(self, request: TraceIngestRequest) -> dict[str, object]:
        impacted_services = {
            span.service for span in request.spans
        } | {log.service for log in request.logs} | {metric.service for metric in request.metrics}
        impacted_services |= {alert.service for alert in request.alerts}
        impacted_services |= {error.service for error in request.errors}
        impacted_services |= {dependency.source for dependency in request.dependencies}
        impacted_services |= {dependency.target for dependency in request.dependencies}

        hot_metrics = [
            {
                "service": metric.service,
                "name": metric.name,
                "value": metric.value,
                "unit": metric.unit,
            }
            for metric in request.metrics
            if metric.value >= 80 or "latency" in metric.name.lower() or "error" in metric.name.lower()
        ]
        critical_alerts = [
            {
                "service": alert.service,
                "name": alert.name,
                "severity": alert.severity,
                "state": alert.state,
            }
            for alert in request.alerts
            if alert.severity.lower() in {"critical", "high"}
        ]

        return {
            "environment": request.environment,
            "tenant": request.tenant,
            "span_count": len(request.spans),
            "log_count": len(request.logs),
            "metric_count": len(request.metrics),
            "alert_count": len(request.alerts),
            "error_count": len(request.errors),
            "deployment_count": len(request.deployments),
            "host_signal_count": len(request.host_signals),
            "dependency_count": len(request.dependencies),
            "impacted_services": sorted(impacted_services),
            "critical_alerts": critical_alerts,
            "hot_metrics": hot_metrics[:8],
            "incident_hints": request.incident_hints,
        }
