from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.models.schemas import (
    AlertRecord,
    DeploymentRecord,
    ErrorRecord,
    HostSignalRecord,
    LogRecord,
    MetricRecord,
    ServiceDependency,
    Span,
    TelemetryTag,
    TraceIngestRequest,
)


class TelemetryNormalizationService:
    def normalize_payload(self, payload: dict[str, Any]) -> TraceIngestRequest:
        provider = str(payload.get("provider", "generic"))
        trace_id = str(payload.get("trace_id") or f"trace-{uuid4().hex[:12]}")
        environment = str(payload.get("environment", "production"))
        tenant = str(payload.get("tenant", "rocketride"))

        spans = [self._normalize_span(item, index) for index, item in enumerate(payload.get("spans", []), start=1)]
        logs = [self._normalize_log(item, index, trace_id, environment) for index, item in enumerate(payload.get("logs", []), start=1)]
        metrics = [
            self._normalize_metric(item, index, environment)
            for index, item in enumerate(payload.get("metrics", []), start=1)
        ]
        alerts = [self._normalize_alert(item, index) for index, item in enumerate(payload.get("alerts", []), start=1)]
        errors = [self._normalize_error(item, index) for index, item in enumerate(payload.get("errors", []), start=1)]
        deployments = [
            self._normalize_deployment(item, index, environment)
            for index, item in enumerate(payload.get("deployments", []), start=1)
        ]
        host_signals = [
            self._normalize_host_signal(item, index)
            for index, item in enumerate(payload.get("host_signals", []), start=1)
        ]
        dependencies = [
            ServiceDependency(source=str(item.get("source", "")).strip(), target=str(item.get("target", "")).strip())
            for item in payload.get("dependencies", [])
            if str(item.get("source", "")).strip() and str(item.get("target", "")).strip()
        ]

        if not spans:
            spans = self._build_fallback_spans(alerts, metrics, logs)

        incident_hints = [str(item).strip() for item in payload.get("incident_hints", []) if str(item).strip()]
        incident_hints.extend(log.message for log in logs if log.level.upper() in {"ERROR", "CRITICAL"})
        incident_hints.extend(alert.description for alert in alerts)

        return TraceIngestRequest(
            provider=provider,
            trace_id=trace_id,
            spans=spans,
            logs=logs,
            metrics=metrics,
            alerts=alerts,
            errors=errors,
            deployments=deployments,
            host_signals=host_signals,
            dependencies=dependencies,
            environment=environment,
            tenant=tenant,
            incident_hints=self._unique(incident_hints)[:10],
        )

    def normalize_payload_to_incident(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = self.normalize_payload(payload)
        affected_services = self._unique(
            [span.service for span in request.spans]
            + [log.service for log in request.logs]
            + [metric.service for metric in request.metrics]
            + [alert.service for alert in request.alerts]
            + [dependency.target for dependency in request.dependencies]
        )
        severity = self._derive_severity(request)
        root_cause_service = self._derive_root_cause_service(request, affected_services)
        primary_service = self._derive_primary_service(request, affected_services)

        return {
            "incident_id": f"INC-{datetime.now(UTC).strftime('%H%M%S')}-{uuid4().hex[:4]}",
            "title": f"{primary_service} incident detected",
            "status": "active",
            "severity": severity,
            "primary_service": primary_service,
            "root_cause_service": root_cause_service,
            "affected_services": affected_services,
            "created_at": self._now_iso(),
            "source": "telemetry",
            "confidence_score": 0.92 if severity == "critical" else 0.81,
        }

    def _normalize_span(self, span: dict[str, Any], index: int) -> Span:
        metadata = dict(span.get("metadata", {}))
        if "latency_ms" in span and "duration_ms" not in span:
            metadata["latency_ms"] = span.get("latency_ms")

        return Span(
            span_id=str(span.get("span_id") or f"span-{index:03d}"),
            parent_id=span.get("parent_id"),
            service=str(span.get("service", "unknown-service")),
            operation=str(span.get("operation") or span.get("name") or f"operation-{index}"),
            status=str(span.get("status", "ok")).lower(),
            duration_ms=float(span.get("duration_ms") or span.get("latency_ms") or 0.0),
            error_type=span.get("error_type") or ("TelemetryError" if str(span.get("status", "")).lower() == "error" else None),
            metadata=metadata,
        )

    def _normalize_log(self, log: dict[str, Any], index: int, trace_id: str, environment: str) -> LogRecord:
        tags = [
            TelemetryTag(key=str(item.get("key")), value=str(item.get("value")))
            for item in log.get("tags", [])
            if item.get("key") is not None and item.get("value") is not None
        ]
        return LogRecord(
            log_id=str(log.get("log_id") or f"log-{index:03d}"),
            timestamp=str(log.get("timestamp") or self._now_iso()),
            service=str(log.get("service", "unknown-service")),
            level=str(log.get("level", "INFO")).upper(),
            message=str(log.get("message", "")),
            logger=log.get("logger"),
            trace_id=str(log.get("trace_id") or trace_id),
            span_id=log.get("span_id"),
            environment=str(log.get("environment") or environment),
            region=log.get("region"),
            tags=tags,
            context=dict(log.get("context", {})),
        )

    def _normalize_metric(self, metric: dict[str, Any], index: int, environment: str) -> MetricRecord:
        dimensions = dict(metric.get("dimensions", {}))
        if "env" not in dimensions:
            dimensions["env"] = environment
        return MetricRecord(
            metric_id=str(metric.get("metric_id") or f"metric-{index:03d}"),
            timestamp=str(metric.get("timestamp") or self._now_iso()),
            service=str(metric.get("service", "unknown-service")),
            name=str(metric.get("name", f"metric-{index}")),
            value=float(metric.get("value", 0.0)),
            unit=str(metric.get("unit", "count")),
            aggregation=metric.get("aggregation"),
            source=metric.get("source"),
            dimensions=dimensions,
        )

    def _normalize_alert(self, alert: dict[str, Any], index: int) -> AlertRecord:
        service = str(alert.get("service", "unknown-service"))
        severity = str(alert.get("severity", "medium")).lower()
        description = str(alert.get("description") or alert.get("message") or f"Alert for {service}")
        return AlertRecord(
            alert_id=str(alert.get("alert_id") or f"alert-{index:03d}"),
            source=str(alert.get("source") or "telemetry"),
            name=str(alert.get("name") or description[:80]),
            severity=severity,
            state=str(alert.get("state") or "triggered"),
            service=service,
            description=description,
            triggered_at=str(alert.get("triggered_at") or alert.get("timestamp") or self._now_iso()),
            runbook_url=alert.get("runbook_url"),
            signal_type=alert.get("signal_type"),
            labels=dict(alert.get("labels", {})),
        )

    def _normalize_error(self, error: dict[str, Any], index: int) -> ErrorRecord:
        return ErrorRecord(
            error_id=str(error.get("error_id") or f"error-{index:03d}"),
            timestamp=str(error.get("timestamp") or self._now_iso()),
            service=str(error.get("service", "unknown-service")),
            error_class=str(error.get("error_class") or error.get("type") or "TelemetryError"),
            error_message=str(error.get("error_message") or error.get("message") or "Unknown error"),
            handled=bool(error.get("handled", False)),
            count=int(error.get("count", 1)),
            endpoint=error.get("endpoint"),
            stacktrace=list(error.get("stacktrace", [])),
            attributes=dict(error.get("attributes", {})),
        )

    def _normalize_deployment(self, deployment: dict[str, Any], index: int, environment: str) -> DeploymentRecord:
        return DeploymentRecord(
            deployment_id=str(deployment.get("deployment_id") or f"deployment-{index:03d}"),
            service=str(deployment.get("service", "unknown-service")),
            version=str(deployment.get("version", "unknown")),
            environment=str(deployment.get("environment") or environment),
            deployed_at=str(deployment.get("deployed_at") or deployment.get("timestamp") or self._now_iso()),
            commit_sha=str(deployment.get("commit_sha") or "unknown"),
            actor=str(deployment.get("actor") or "telemetry"),
            strategy=str(deployment.get("strategy") or "unspecified"),
            change_summary=str(deployment.get("change_summary") or "Telemetry-derived deployment signal"),
        )

    def _normalize_host_signal(self, host_signal: dict[str, Any], index: int) -> HostSignalRecord:
        hostname = str(host_signal.get("hostname") or host_signal.get("host") or f"host-{index}")
        return HostSignalRecord(
            host_id=str(host_signal.get("host_id") or hostname),
            hostname=hostname,
            service=str(host_signal.get("service", "unknown-service")),
            region=str(host_signal.get("region", "unknown-region")),
            cpu_pct=float(host_signal.get("cpu_pct") or host_signal.get("cpu_usage") or 0.0),
            memory_pct=float(host_signal.get("memory_pct") or host_signal.get("memory_usage") or 0.0),
            disk_pct=float(host_signal.get("disk_pct") or 0.0),
            network_error_rate=float(host_signal.get("network_error_rate") or 0.0),
            pod_restarts=int(host_signal.get("pod_restarts") or 0),
            node_status=str(host_signal.get("node_status") or "healthy"),
        )

    def _build_fallback_spans(
        self,
        alerts: list[AlertRecord],
        metrics: list[MetricRecord],
        logs: list[LogRecord],
    ) -> list[Span]:
        services = self._unique([alert.service for alert in alerts] + [metric.service for metric in metrics] + [log.service for log in logs])
        return [
            Span(
                span_id=f"generated-span-{index:03d}",
                service=service,
                operation="telemetry-observation",
                status="error" if any(alert.service == service and alert.severity == "critical" for alert in alerts) else "ok",
                duration_ms=0.0,
            )
            for index, service in enumerate(services, start=1)
        ]

    def _derive_severity(self, request: TraceIngestRequest) -> str:
        alert_levels = {alert.severity.lower() for alert in request.alerts}
        if "critical" in alert_levels:
            return "critical"
        if "high" in alert_levels:
            return "high"
        if any(span.status in {"error", "timeout"} for span in request.spans):
            return "high"
        return "medium"

    def _derive_primary_service(self, request: TraceIngestRequest, affected_services: list[str]) -> str:
        for service in [request.spans[0].service if request.spans else None, request.alerts[0].service if request.alerts else None]:
            if service:
                return service
        return affected_services[0] if affected_services else "unknown-service"

    def _derive_root_cause_service(self, request: TraceIngestRequest, affected_services: list[str]) -> str:
        for service in [request.errors[0].service if request.errors else None, request.logs[0].service if request.logs else None]:
            if service:
                return service
        return affected_services[0] if affected_services else "unknown-service"

    def _unique(self, values: list[str]) -> list[str]:
        output: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not value or value in seen:
                continue
            seen.add(value)
            output.append(value)
        return output

    def _now_iso(self) -> str:
        return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
