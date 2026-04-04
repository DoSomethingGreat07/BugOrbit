from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from app.models.schemas import (
    AlertRecord,
    LiveTelemetryAlert,
    LiveTelemetryLog,
    LiveTelemetryMetric,
    LiveTelemetryRequest,
    LiveTelemetrySpan,
    LogRecord,
    MetricRecord,
    Span,
    TelemetryTag,
    TraceIngestRequest,
)


class LiveTelemetryAdapterService:
    def normalize(self, request: LiveTelemetryRequest) -> TraceIngestRequest:
        trace_id = request.trace_id or self._resolve_trace_id(request)
        environment = request.environment or str(request.resource_attributes.get("deployment.environment", "production"))

        spans = [self._normalize_span(span, request, trace_id) for span in request.spans]
        logs = [self._normalize_log(log, request, trace_id, environment) for log in request.logs]
        metrics = [self._normalize_metric(metric, request) for metric in request.metrics]
        alerts = [self._normalize_alert(alert, request) for alert in request.alerts]

        incident_hints = list(request.incident_hints)
        incident_hints.extend(
            log.message for log in logs if log.level.upper() in {"ERROR", "CRITICAL"}
        )
        incident_hints.extend(alert.description for alert in alerts)

        return TraceIngestRequest(
            provider=request.provider,
            trace_id=trace_id,
            spans=spans,
            logs=logs,
            metrics=metrics,
            alerts=alerts,
            environment=environment,
            tenant=request.tenant,
            incident_hints=incident_hints[:6],
        )

    def _normalize_span(
        self,
        span: LiveTelemetrySpan,
        request: LiveTelemetryRequest,
        trace_id: str,
    ) -> Span:
        service_name = self._resolve_service_name(
            explicit=span.service_name,
            attributes=span.attributes,
            request=request,
        )
        error_type = self._resolve_error_type(span)
        duration_ms = span.duration_ms if span.duration_ms is not None else self._duration_from_timestamps(
            span.start_time,
            span.end_time,
        )

        metadata = dict(span.attributes)
        if span.events:
            metadata["events"] = [
                {
                    "name": event.name,
                    "timestamp": event.timestamp,
                    "attributes": event.attributes,
                }
                for event in span.events
            ]
        metadata["trace_id"] = span.trace_id or trace_id

        return Span(
            span_id=span.span_id,
            parent_id=span.parent_span_id,
            service=service_name,
            operation=span.name,
            status=span.status.lower(),
            duration_ms=duration_ms,
            error_type=error_type,
            metadata=metadata,
        )

    def _normalize_log(
        self,
        log: LiveTelemetryLog,
        request: LiveTelemetryRequest,
        trace_id: str,
        environment: str,
    ) -> LogRecord:
        service_name = self._resolve_service_name(
            explicit=log.service_name,
            attributes=log.attributes,
            request=request,
        )
        return LogRecord(
            log_id=log.log_id or f"log-{uuid4().hex[:12]}",
            timestamp=log.timestamp,
            service=service_name,
            level=log.level.upper(),
            message=log.message,
            logger=log.logger,
            trace_id=log.trace_id or trace_id,
            span_id=log.span_id,
            environment=environment,
            region=log.region or self._resource_value(request, "cloud.region"),
            tags=self._attributes_to_tags(log.attributes),
            context=log.attributes,
        )

    def _normalize_metric(self, metric: LiveTelemetryMetric, request: LiveTelemetryRequest) -> MetricRecord:
        service_name = self._resolve_service_name(
            explicit=metric.service_name,
            attributes=metric.attributes,
            request=request,
        )
        return MetricRecord(
            metric_id=metric.metric_id or f"metric-{uuid4().hex[:12]}",
            timestamp=metric.timestamp,
            service=service_name,
            name=metric.name,
            value=metric.value,
            unit=metric.unit,
            aggregation=metric.aggregation,
            source=metric.source or request.provider,
            dimensions=metric.attributes,
        )

    def _normalize_alert(self, alert: LiveTelemetryAlert, request: LiveTelemetryRequest) -> AlertRecord:
        service_name = self._resolve_service_name(
            explicit=alert.service_name,
            attributes=alert.labels,
            request=request,
        )
        return AlertRecord(
            alert_id=alert.alert_id or f"alert-{uuid4().hex[:12]}",
            source=alert.source,
            name=alert.name,
            severity=alert.severity,
            state=alert.state,
            service=service_name,
            description=alert.description,
            triggered_at=alert.triggered_at,
            runbook_url=alert.runbook_url,
            signal_type=alert.signal_type,
            labels=alert.labels,
        )

    def _resolve_trace_id(self, request: LiveTelemetryRequest) -> str:
        if request.spans and request.spans[0].trace_id:
            return request.spans[0].trace_id
        if request.logs and request.logs[0].trace_id:
            return request.logs[0].trace_id
        return f"live-trace-{uuid4().hex[:12]}"

    def _resolve_service_name(
        self,
        explicit: str | None,
        attributes: dict[str, Any],
        request: LiveTelemetryRequest,
    ) -> str:
        for candidate in (
            explicit,
            self._attribute_value(attributes, "service.name"),
            self._attribute_value(attributes, "service"),
            request.service_name,
            self._resource_value(request, "service.name"),
        ):
            if candidate:
                return str(candidate)
        return "unknown-service"

    def _resolve_error_type(self, span: LiveTelemetrySpan) -> str | None:
        if span.status.lower() == "error":
            for event in span.events:
                if event.name.lower() == "exception":
                    exception_type = self._attribute_value(event.attributes, "exception.type")
                    if exception_type:
                        return str(exception_type)
            span_error = self._attribute_value(span.attributes, "error.type")
            if span_error:
                return str(span_error)
            return "SpanError"
        return None

    def _duration_from_timestamps(self, start_time: str | None, end_time: str | None) -> float:
        if not start_time or not end_time:
            return 0.0
        try:
            start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        except ValueError:
            return 0.0
        return max(0.0, (end - start).total_seconds() * 1000)

    def _attributes_to_tags(self, attributes: dict[str, Any]) -> list[TelemetryTag]:
        return [
            TelemetryTag(key=str(key), value=str(value))
            for key, value in attributes.items()
            if value is not None
        ]

    def _resource_value(self, request: LiveTelemetryRequest, key: str) -> Any:
        return self._attribute_value(request.resource_attributes, key)

    def _attribute_value(self, attributes: dict[str, Any], key: str) -> Any:
        return attributes.get(key) if attributes else None

