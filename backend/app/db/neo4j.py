from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from neo4j import Driver, GraphDatabase
from neo4j.exceptions import Neo4jError

from app.core.config import settings
from app.models.schemas import (
    AlertRecord,
    GraphQueryResult,
    HostSignalRecord,
    ImpactAnalysis,
    IncidentRecord,
    LogRecord,
    MetricRecord,
    DeploymentRecord,
    RuntimeIncidentRecord,
    RuntimeResolutionStep,
    ServiceDependency,
    Span,
    StructuredTrace,
    TraceAnalysis,
    TraceIngestRequest,
)

logger = logging.getLogger(__name__)


class Neo4jService:
    """
    Real Neo4j adapter with a safe fallback to demo data when the database is
    unavailable. The graph stores both topology and incident evidence so future
    queries can use trace-derived relationships instead of a hardcoded map.
    """

    _fallback_dependency_map = {
        "payment-service": ["checkout-service", "ledger-service", "notification-service"],
        "checkout-service": ["cart-service", "inventory-service"],
        "api-gateway": ["auth-service", "payment-service", "search-service"],
        "inventory-service": ["catalog-db", "pricing-service"],
    }

    def __init__(self) -> None:
        self._driver: Driver | None = None
        self._schema_ready = False
        self._bootstrapped = False

    def query_impacted_services(self, service_name: str, cypher: str) -> GraphQueryResult:
        records = self._run_read(
            """
            MATCH (s:Service {name: $service_name})
            OPTIONAL MATCH path=(s)-[:DEPENDS_ON|CALLS*1..3]->(dep:Service)
            WITH collect(DISTINCT dep.name) AS affected, collect(DISTINCT path) AS raw_paths
            RETURN affected, raw_paths
            """,
            {"service_name": service_name},
        )
        if records:
            row = records[0]
            affected_services = [name for name in row.get("affected", []) if name]
            relationships = self._relationships_from_paths(service_name, row.get("raw_paths", []))
            return GraphQueryResult(
                cypher=cypher,
                affected_services=affected_services,
                relationships=relationships,
            )

        affected = self._fallback_dependency_map.get(service_name, [])
        relationships = [{"source": service_name, "target": dep} for dep in affected]
        return GraphQueryResult(cypher=cypher, affected_services=affected, relationships=relationships)

    def sync_trace_graph(
        self,
        request: TraceIngestRequest,
        structured_trace: StructuredTrace,
        trace_analysis: TraceAnalysis,
    ) -> None:
        timestamp = self._now_iso()
        operations = [
            ("MERGE (t:Tenant {name: $tenant})", {"tenant": request.tenant}),
            (
                """
                MERGE (tr:Trace {trace_id: $trace_id})
                SET tr.provider = $provider,
                    tr.environment = $environment,
                    tr.root_service = $root_service,
                    tr.root_endpoint = $root_endpoint,
                    tr.error_type = $error_type,
                    tr.latency_ms = $latency_ms,
                    tr.failure_point = $failure_point,
                    tr.updated_at = $updated_at
                """,
                {
                    "trace_id": structured_trace.trace_id,
                    "provider": structured_trace.provider,
                    "environment": request.environment,
                    "root_service": structured_trace.root_service,
                    "root_endpoint": structured_trace.root_endpoint,
                    "error_type": structured_trace.error_type,
                    "latency_ms": structured_trace.latency_ms,
                    "failure_point": trace_analysis.failure_point,
                    "updated_at": timestamp,
                },
            ),
            (
                """
                MATCH (t:Tenant {name: $tenant})
                MATCH (tr:Trace {trace_id: $trace_id})
                MERGE (t)-[:OWNS_TRACE]->(tr)
                """,
                {"tenant": request.tenant, "trace_id": structured_trace.trace_id},
            ),
        ]

        for service in structured_trace.telemetry_summary.get("impacted_services", []):
            operations.extend(self._service_operations(service, request, structured_trace, trace_analysis, timestamp))

        for span in request.spans:
            operations.extend(self._span_operations(span, request, structured_trace.trace_id, timestamp))

        for log in request.logs:
            operations.extend(self._log_operations(log, structured_trace.trace_id, timestamp))

        for metric in request.metrics:
            operations.extend(self._metric_operations(metric, structured_trace.trace_id, timestamp))

        for alert in request.alerts:
            operations.extend(self._alert_operations(alert, structured_trace.trace_id, timestamp))

        for deployment in request.deployments:
            operations.extend(self._deployment_operations(deployment, timestamp))

        for host_signal in request.host_signals:
            operations.extend(self._host_signal_operations(host_signal, timestamp))

        for dependency in request.dependencies:
            operations.extend(self._dependency_operations(dependency, timestamp))

        self._run_write_batch(operations)

    def sync_analysis_graph(
        self,
        structured_trace: StructuredTrace,
        trace_analysis: TraceAnalysis,
        graph_result: GraphQueryResult,
        impact_analysis: ImpactAnalysis,
        incident_matches: list[IncidentRecord],
        root_cause: str,
        confidence_score: float,
        solutions: list[str],
    ) -> None:
        timestamp = self._now_iso()
        operations: list[tuple[str, dict[str, Any]]] = [
            (
                """
                MATCH (tr:Trace {trace_id: $trace_id})
                SET tr.failure_summary = $summary,
                    tr.root_cause = $root_cause,
                    tr.confidence_score = $confidence_score,
                    tr.blast_radius = $blast_radius,
                    tr.severity = $severity,
                    tr.recommended_actions = $solutions,
                    tr.updated_at = $updated_at
                """,
                {
                    "trace_id": structured_trace.trace_id,
                    "summary": trace_analysis.summary,
                    "root_cause": root_cause,
                    "confidence_score": confidence_score,
                    "blast_radius": impact_analysis.blast_radius,
                    "severity": impact_analysis.severity,
                    "solutions": solutions,
                    "updated_at": timestamp,
                },
            ),
        ]

        for suspected_issue in trace_analysis.suspected_issues:
            operations.append(
                (
                    """
                    MATCH (tr:Trace {trace_id: $trace_id})
                    MERGE (h:Hypothesis {trace_id: $trace_id, text: $text})
                    SET h.updated_at = $updated_at
                    MERGE (tr)-[:HAS_HYPOTHESIS]->(h)
                    """,
                    {"trace_id": structured_trace.trace_id, "text": suspected_issue, "updated_at": timestamp},
                )
            )

        for relationship in graph_result.relationships:
            operations.append(
                (
                    """
                    MATCH (source:Service {name: $source})
                    MATCH (target:Service {name: $target})
                    MERGE (source)-[r:IMPACTS {trace_id: $trace_id}]->(target)
                    SET r.updated_at = $updated_at
                    """,
                    {
                        "source": relationship["source"],
                        "target": relationship["target"],
                        "trace_id": structured_trace.trace_id,
                        "updated_at": timestamp,
                    },
                )
            )

        for incident in incident_matches:
            operations.extend(self._incident_operations(incident, structured_trace.trace_id, timestamp))

        self._run_write_batch(operations)

    def sync_runtime_incident(self, incident: RuntimeIncidentRecord) -> None:
        operations: list[tuple[str, dict[str, Any]]] = [
            (
                """
                MERGE (inc:Incident {incident_id: $incident_id})
                SET inc.title = $title,
                    inc.status = $status,
                    inc.severity = $severity,
                    inc.primary_service = $primary_service,
                    inc.root_cause = $root_cause,
                    inc.root_cause_service = $root_cause_service,
                    inc.source = 'telemetry',
                    inc.confidence_score = $confidence_score,
                    inc.created_at = $created_at,
                    inc.updated_at = $updated_at
                """,
                {
                    "incident_id": incident.id,
                    "title": incident.title,
                    "status": incident.status,
                    "severity": incident.severity,
                    "primary_service": incident.primary_service,
                    "root_cause": incident.root_cause,
                    "root_cause_service": incident.root_cause_service,
                    "confidence_score": incident.confidence,
                    "created_at": incident.time_started,
                    "updated_at": self._now_iso(),
                },
            )
        ]

        for service in incident.propagation_path:
            operations.extend(
                [
                    ("MERGE (s:Service {name: $service})", {"service": service}),
                    (
                        """
                        MATCH (inc:Incident {incident_id: $incident_id})
                        MATCH (s:Service {name: $service})
                        MERGE (inc)-[:AFFECTS]->(s)
                        """,
                        {"incident_id": incident.id, "service": service},
                    ),
                ]
            )

        if incident.root_cause_service:
            operations.append(
                (
                    """
                    MATCH (inc:Incident {incident_id: $incident_id})
                    MATCH (s:Service {name: $service})
                    MERGE (inc)-[:ROOT_CAUSE]->(s)
                    """,
                    {"incident_id": incident.id, "service": incident.root_cause_service},
                )
            )

        self._run_write_batch(operations)

    def sync_incident_fix(
        self,
        incident_id: str,
        trace_id: str,
        services: list[str],
        resolution_step: RuntimeResolutionStep,
    ) -> None:
        operations: list[tuple[str, dict[str, Any]]] = [
            (
                """
                MERGE (fix:FixAction {fix_id: $fix_id})
                SET fix.action = $action,
                    fix.actor = $actor,
                    fix.timestamp = $timestamp,
                    fix.result = $result,
                    fix.feedback = $feedback,
                    fix.notes = $notes
                """,
                {
                    "fix_id": f"{incident_id}-fix-{resolution_step.step}",
                    "action": resolution_step.action,
                    "actor": resolution_step.actor,
                    "timestamp": resolution_step.timestamp,
                    "result": resolution_step.result,
                    "feedback": resolution_step.feedback,
                    "notes": resolution_step.notes,
                },
            ),
            (
                """
                MATCH (inc:Incident {incident_id: $incident_id})
                MATCH (fix:FixAction {fix_id: $fix_id})
                MERGE (inc)-[:HAS_FIX_ACTION]->(fix)
                SET inc.status = 'active',
                    inc.last_fix_at = $timestamp
                """,
                {
                    "incident_id": incident_id,
                    "fix_id": f"{incident_id}-fix-{resolution_step.step}",
                    "timestamp": resolution_step.timestamp,
                },
            ),
            (
                """
                MATCH (tr:Trace {trace_id: $trace_id})
                SET tr.incident_status = 'active',
                    tr.last_fix_at = $timestamp
                """,
                {"trace_id": trace_id, "timestamp": resolution_step.timestamp},
            ),
        ]
        for service in services:
            operations.append(
                (
                    """
                    MERGE (s:Service {name: $service})
                    SET s.last_incident_status = 'active',
                        s.last_fix_at = $timestamp
                    """,
                    {"service": service, "timestamp": resolution_step.timestamp},
                )
            )
        self._run_write_batch(operations)

    def sync_incident_resolution(
        self,
        incident_id: str,
        trace_id: str,
        services: list[str],
        incident: RuntimeIncidentRecord,
    ) -> None:
        operations: list[tuple[str, dict[str, Any]]] = [
            (
                """
                MATCH (inc:Incident {incident_id: $incident_id})
                SET inc.status = 'resolved',
                    inc.resolved_at = $resolved_at,
                    inc.final_resolution = $final_resolution,
                    inc.resolved_by = $resolved_by,
                    inc.resolution_type = $resolution_type,
                    inc.post_fix_validation = $post_fix_validation
                """,
                {
                    "incident_id": incident_id,
                    "resolved_at": incident.resolved_at,
                    "final_resolution": incident.final_resolution,
                    "resolved_by": incident.resolved_by,
                    "resolution_type": incident.resolution_type,
                    "post_fix_validation": incident.post_fix_validation,
                },
            ),
            (
                """
                MATCH (tr:Trace {trace_id: $trace_id})
                SET tr.incident_status = 'resolved',
                    tr.resolved_at = $resolved_at,
                    tr.final_resolution = $final_resolution
                """,
                {
                    "trace_id": trace_id,
                    "resolved_at": incident.resolved_at,
                    "final_resolution": incident.final_resolution,
                },
            ),
        ]
        for service in services:
            operations.append(
                (
                    """
                    MERGE (s:Service {name: $service})
                    SET s.last_incident_status = 'resolved',
                        s.last_resolved_at = $resolved_at
                    """,
                    {"service": service, "resolved_at": incident.resolved_at},
                )
            )
        self._run_write_batch(operations)

    def _service_operations(
        self,
        service: str,
        request: TraceIngestRequest,
        structured_trace: StructuredTrace,
        trace_analysis: TraceAnalysis,
        timestamp: str,
    ) -> list[tuple[str, dict[str, Any]]]:
        critical_alerts = [a["name"] for a in structured_trace.telemetry_summary.get("critical_alerts", []) if a["service"] == service]
        hot_metrics = [m["name"] for m in structured_trace.telemetry_summary.get("hot_metrics", []) if m["service"] == service]
        return [
            (
                """
                MERGE (s:Service {name: $service})
                SET s.environment = $environment,
                    s.tenant = $tenant,
                    s.last_trace_id = $trace_id,
                    s.last_seen_at = $updated_at,
                    s.last_error_type = $error_type,
                    s.is_failure_point = $is_failure_point,
                    s.critical_alerts = $critical_alerts,
                    s.hot_metrics = $hot_metrics
                """,
                {
                    "service": service,
                    "environment": request.environment,
                    "tenant": request.tenant,
                    "trace_id": structured_trace.trace_id,
                    "updated_at": timestamp,
                    "error_type": structured_trace.error_type,
                    "is_failure_point": service == trace_analysis.failure_point,
                    "critical_alerts": critical_alerts,
                    "hot_metrics": hot_metrics,
                },
            ),
            (
                """
                MATCH (tr:Trace {trace_id: $trace_id})
                MATCH (s:Service {name: $service})
                MERGE (tr)-[:TOUCHED]->(s)
                """,
                {"trace_id": structured_trace.trace_id, "service": service},
            ),
        ]

    def _span_operations(
        self,
        span: Span,
        request: TraceIngestRequest,
        trace_id: str,
        timestamp: str,
    ) -> list[tuple[str, dict[str, Any]]]:
        operations: list[tuple[str, dict[str, Any]]] = [
            (
                """
                MERGE (sp:Span {span_id: $span_id})
                SET sp.trace_id = $trace_id,
                    sp.service = $service,
                    sp.operation = $operation,
                    sp.status = $status,
                    sp.duration_ms = $duration_ms,
                    sp.error_type = $error_type,
                    sp.parent_id = $parent_id,
                    sp.metadata = $metadata,
                    sp.updated_at = $updated_at
                """,
                {
                    "span_id": span.span_id,
                    "trace_id": trace_id,
                    "service": span.service,
                    "operation": span.operation,
                    "status": span.status,
                    "duration_ms": span.duration_ms,
                    "error_type": span.error_type,
                    "parent_id": span.parent_id,
                    "metadata": self._json(span.metadata),
                    "updated_at": timestamp,
                },
            ),
            (
                """
                MATCH (tr:Trace {trace_id: $trace_id})
                MATCH (sp:Span {span_id: $span_id})
                MERGE (tr)-[:HAS_SPAN]->(sp)
                """,
                {"trace_id": trace_id, "span_id": span.span_id},
            ),
            (
                """
                MERGE (s:Service {name: $service})
                SET s.environment = $environment,
                    s.tenant = $tenant,
                    s.last_seen_at = $updated_at
                """,
                {
                    "service": span.service,
                    "environment": request.environment,
                    "tenant": request.tenant,
                    "updated_at": timestamp,
                },
            ),
            (
                """
                MATCH (s:Service {name: $service})
                MATCH (sp:Span {span_id: $span_id})
                MERGE (s)-[:EMITTED_SPAN]->(sp)
                """,
                {"service": span.service, "span_id": span.span_id},
            ),
        ]

        if span.parent_id:
            operations.append(
                (
                    """
                    MATCH (parent:Span {span_id: $parent_id})
                    MATCH (child:Span {span_id: $span_id})
                    MERGE (parent)-[:PARENT_OF]->(child)
                    """,
                    {"parent_id": span.parent_id, "span_id": span.span_id},
                )
            )
            operations.append(
                (
                    """
                    MATCH (parent:Span {span_id: $parent_id})
                    MATCH (caller:Service {name: parent.service})
                    MATCH (callee:Service {name: $service})
                    MERGE (caller)-[r:CALLS]->(callee)
                    SET r.last_trace_id = $trace_id,
                        r.last_operation = $operation,
                        r.last_seen_at = $updated_at,
                        r.error_type = $error_type
                    """,
                    {
                        "parent_id": span.parent_id,
                        "service": span.service,
                        "trace_id": trace_id,
                        "operation": span.operation,
                        "updated_at": timestamp,
                        "error_type": span.error_type,
                    },
                )
            )

        return operations

    def _log_operations(self, log: LogRecord, trace_id: str, timestamp: str) -> list[tuple[str, dict[str, Any]]]:
        return [
            (
                """
                MERGE (l:Log {log_id: $log_id})
                SET l.timestamp = $timestamp,
                    l.level = $level,
                    l.message = $message,
                    l.logger = $logger,
                    l.trace_id = $trace_id,
                    l.span_id = $span_id,
                    l.environment = $environment,
                    l.region = $region,
                    l.context = $context,
                    l.updated_at = $updated_at
                """,
                {
                    "log_id": log.log_id,
                    "timestamp": log.timestamp,
                    "level": log.level,
                    "message": log.message,
                    "logger": log.logger,
                    "trace_id": trace_id,
                    "span_id": log.span_id,
                    "environment": log.environment,
                    "region": log.region,
                    "context": self._json(log.context),
                    "updated_at": timestamp,
                },
            ),
            (
                "MERGE (s:Service {name: $service})",
                {"service": log.service},
            ),
            (
                """
                MATCH (s:Service {name: $service})
                MATCH (l:Log {log_id: $log_id})
                MERGE (s)-[:EMITTED_LOG]->(l)
                """,
                {"service": log.service, "log_id": log.log_id},
            ),
        ]

    def _metric_operations(self, metric: MetricRecord, trace_id: str, timestamp: str) -> list[tuple[str, dict[str, Any]]]:
        return [
            (
                """
                MERGE (m:Metric {metric_id: $metric_id})
                SET m.timestamp = $timestamp,
                    m.name = $name,
                    m.value = $value,
                    m.unit = $unit,
                    m.aggregation = $aggregation,
                    m.source = $source,
                    m.dimensions = $dimensions,
                    m.trace_id = $trace_id,
                    m.updated_at = $updated_at
                """,
                {
                    "metric_id": metric.metric_id,
                    "timestamp": metric.timestamp,
                    "name": metric.name,
                    "value": metric.value,
                    "unit": metric.unit,
                    "aggregation": metric.aggregation,
                    "source": metric.source,
                    "dimensions": self._json(metric.dimensions),
                    "trace_id": trace_id,
                    "updated_at": timestamp,
                },
            ),
            (
                """
                MERGE (s:Service {name: $service})
                SET s.last_seen_at = $updated_at
                """,
                {"service": metric.service, "updated_at": timestamp},
            ),
            (
                """
                MATCH (s:Service {name: $service})
                MATCH (m:Metric {metric_id: $metric_id})
                MERGE (s)-[:OBSERVED_METRIC]->(m)
                """,
                {"service": metric.service, "metric_id": metric.metric_id},
            ),
        ]

    def _alert_operations(self, alert: AlertRecord, trace_id: str, timestamp: str) -> list[tuple[str, dict[str, Any]]]:
        return [
            (
                """
                MERGE (a:Alert {alert_id: $alert_id})
                SET a.source = $source,
                    a.name = $name,
                    a.severity = $severity,
                    a.state = $state,
                    a.description = $description,
                    a.triggered_at = $triggered_at,
                    a.runbook_url = $runbook_url,
                    a.signal_type = $signal_type,
                    a.labels = $labels,
                    a.trace_id = $trace_id,
                    a.updated_at = $updated_at
                """,
                {
                    "alert_id": alert.alert_id,
                    "source": alert.source,
                    "name": alert.name,
                    "severity": alert.severity,
                    "state": alert.state,
                    "description": alert.description,
                    "triggered_at": alert.triggered_at,
                    "runbook_url": alert.runbook_url,
                    "signal_type": alert.signal_type,
                    "labels": self._json(alert.labels),
                    "trace_id": trace_id,
                    "updated_at": timestamp,
                },
            ),
            (
                """
                MERGE (s:Service {name: $service})
                SET s.last_seen_at = $updated_at
                """,
                {"service": alert.service, "updated_at": timestamp},
            ),
            (
                """
                MATCH (s:Service {name: $service})
                MATCH (a:Alert {alert_id: $alert_id})
                MERGE (a)-[:TRIGGERED_FOR]->(s)
                """,
                {"service": alert.service, "alert_id": alert.alert_id},
            ),
        ]

    def _deployment_operations(self, deployment: DeploymentRecord, timestamp: str) -> list[tuple[str, dict[str, Any]]]:
        return [
            (
                """
                MERGE (d:Deployment {deployment_id: $deployment_id})
                SET d.version = $version,
                    d.environment = $environment,
                    d.deployed_at = $deployed_at,
                    d.commit_sha = $commit_sha,
                    d.actor = $actor,
                    d.strategy = $strategy,
                    d.change_summary = $change_summary,
                    d.updated_at = $updated_at
                """,
                {
                    "deployment_id": deployment.deployment_id,
                    "version": deployment.version,
                    "environment": deployment.environment,
                    "deployed_at": deployment.deployed_at,
                    "commit_sha": deployment.commit_sha,
                    "actor": deployment.actor,
                    "strategy": deployment.strategy,
                    "change_summary": deployment.change_summary,
                    "updated_at": timestamp,
                },
            ),
            (
                "MERGE (s:Service {name: $service})",
                {"service": deployment.service},
            ),
            (
                """
                MATCH (s:Service {name: $service})
                MATCH (d:Deployment {deployment_id: $deployment_id})
                MERGE (s)-[:DEPLOYED_AS]->(d)
                """,
                {"service": deployment.service, "deployment_id": deployment.deployment_id},
            ),
        ]

    def _host_signal_operations(self, host_signal: HostSignalRecord, timestamp: str) -> list[tuple[str, dict[str, Any]]]:
        return [
            (
                """
                MERGE (h:Host {host_id: $host_id})
                SET h.hostname = $hostname,
                    h.region = $region,
                    h.cpu_pct = $cpu_pct,
                    h.memory_pct = $memory_pct,
                    h.disk_pct = $disk_pct,
                    h.network_error_rate = $network_error_rate,
                    h.pod_restarts = $pod_restarts,
                    h.node_status = $node_status,
                    h.updated_at = $updated_at
                """,
                {
                    "host_id": host_signal.host_id,
                    "hostname": host_signal.hostname,
                    "region": host_signal.region,
                    "cpu_pct": host_signal.cpu_pct,
                    "memory_pct": host_signal.memory_pct,
                    "disk_pct": host_signal.disk_pct,
                    "network_error_rate": host_signal.network_error_rate,
                    "pod_restarts": host_signal.pod_restarts,
                    "node_status": host_signal.node_status,
                    "updated_at": timestamp,
                },
            ),
            (
                "MERGE (s:Service {name: $service})",
                {"service": host_signal.service},
            ),
            (
                """
                MATCH (s:Service {name: $service})
                MATCH (h:Host {host_id: $host_id})
                MERGE (s)-[:RUNS_ON]->(h)
                """,
                {"service": host_signal.service, "host_id": host_signal.host_id},
            ),
        ]

    def _dependency_operations(self, dependency: ServiceDependency, timestamp: str) -> list[tuple[str, dict[str, Any]]]:
        return [
            ("MERGE (source:Service {name: $source})", {"source": dependency.source}),
            ("MERGE (target:Service {name: $target})", {"target": dependency.target}),
            (
                """
                MATCH (source:Service {name: $source})
                MATCH (target:Service {name: $target})
                MERGE (source)-[r:DEPENDS_ON]->(target)
                SET r.last_seen_at = $updated_at,
                    r.source = 'normalized-payload'
                """,
                {"source": dependency.source, "target": dependency.target, "updated_at": timestamp},
            ),
        ]

    def _incident_operations(self, incident: IncidentRecord, trace_id: str, timestamp: str) -> list[tuple[str, dict[str, Any]]]:
        operations: list[tuple[str, dict[str, Any]]] = [
            (
                """
                MERGE (inc:Incident {incident_id: $incident_id})
                SET inc.title = $title,
                    inc.summary = $summary,
                    inc.root_cause = $root_cause,
                    inc.symptoms = $symptoms,
                    inc.fixes = $fixes,
                    inc.updated_at = $updated_at
                """,
                {
                    "incident_id": incident.incident_id,
                    "title": incident.title,
                    "summary": incident.summary,
                    "root_cause": incident.root_cause,
                    "symptoms": incident.symptoms,
                    "fixes": incident.fix,
                    "updated_at": timestamp,
                },
            ),
            (
                """
                MATCH (tr:Trace {trace_id: $trace_id})
                MATCH (inc:Incident {incident_id: $incident_id})
                MERGE (tr)-[:SIMILAR_TO]->(inc)
                """,
                {"trace_id": trace_id, "incident_id": incident.incident_id},
            ),
        ]
        for service in incident.services:
            operations.extend(
                [
                    (
                        "MERGE (s:Service {name: $service})",
                        {"service": service},
                    ),
                    (
                        """
                        MATCH (inc:Incident {incident_id: $incident_id})
                        MATCH (s:Service {name: $service})
                        MERGE (inc)-[:INVOLVES]->(s)
                        """,
                        {"incident_id": incident.incident_id, "service": service},
                    ),
                ]
            )
        return operations

    def _run_read(self, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        if not self._driver_ready():
            return []
        try:
            assert self._driver is not None
            with self._driver.session(database=settings.neo4j_database) as session:
                result = session.run(cypher, params)
                return [record.data() for record in result]
        except Neo4jError as exc:
            logger.exception("Neo4j read failed: %s", exc)
            return []

    def _run_write_batch(self, operations: Iterable[tuple[str, dict[str, Any]]]) -> None:
        if not self._driver_ready():
            return
        self._execute_write_batch(operations)

    def _execute_write_batch(self, operations: Iterable[tuple[str, dict[str, Any]]]) -> None:
        try:
            assert self._driver is not None
            with self._driver.session(database=settings.neo4j_database) as session:
                for cypher, params in operations:
                    session.run(cypher, params).consume()
        except Neo4jError as exc:
            logger.exception("Neo4j write failed: %s", exc)
            return

    def _driver_ready(self) -> bool:
        if not settings.neo4j_enabled:
            logger.warning("Neo4j disabled via NEO4J_ENABLED=false; using fallback dependency map.")
            return False
        if self._driver is None:
            try:
                self._driver = GraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_username, settings.neo4j_password),
                )
                self._driver.verify_connectivity()
                logger.info("Connected to Neo4j at %s", settings.neo4j_uri)
            except Exception as exc:
                logger.exception("Neo4j connectivity check failed for %s: %s", settings.neo4j_uri, exc)
                self._driver = None
                return False
        if not self._schema_ready:
            self._ensure_schema()
        if settings.neo4j_bootstrap_demo_data and not self._bootstrapped:
            self._bootstrap_demo_data()
        return self._driver is not None

    def _ensure_schema(self) -> None:
        statements = [
            "CREATE CONSTRAINT service_name IF NOT EXISTS FOR (s:Service) REQUIRE s.name IS UNIQUE",
            "CREATE CONSTRAINT trace_id IF NOT EXISTS FOR (t:Trace) REQUIRE t.trace_id IS UNIQUE",
            "CREATE CONSTRAINT incident_id IF NOT EXISTS FOR (i:Incident) REQUIRE i.incident_id IS UNIQUE",
            "CREATE CONSTRAINT alert_id IF NOT EXISTS FOR (a:Alert) REQUIRE a.alert_id IS UNIQUE",
            "CREATE CONSTRAINT metric_id IF NOT EXISTS FOR (m:Metric) REQUIRE m.metric_id IS UNIQUE",
            "CREATE CONSTRAINT span_id IF NOT EXISTS FOR (s:Span) REQUIRE s.span_id IS UNIQUE",
            "CREATE CONSTRAINT log_id IF NOT EXISTS FOR (l:Log) REQUIRE l.log_id IS UNIQUE",
            "CREATE CONSTRAINT deployment_id IF NOT EXISTS FOR (d:Deployment) REQUIRE d.deployment_id IS UNIQUE",
            "CREATE CONSTRAINT host_id IF NOT EXISTS FOR (h:Host) REQUIRE h.host_id IS UNIQUE",
            "CREATE CONSTRAINT tenant_name IF NOT EXISTS FOR (t:Tenant) REQUIRE t.name IS UNIQUE",
        ]
        try:
            assert self._driver is not None
            with self._driver.session(database=settings.neo4j_database) as session:
                for statement in statements:
                    session.run(statement).consume()
            self._schema_ready = True
            logger.info("Neo4j schema ensured for database %s", settings.neo4j_database)
        except Neo4jError as exc:
            logger.exception("Neo4j schema setup failed: %s", exc)
            self._schema_ready = False

    def _bootstrap_demo_data(self) -> None:
        operations: list[tuple[str, dict[str, Any]]] = []
        timestamp = self._now_iso()
        for source, targets in self._fallback_dependency_map.items():
            operations.append(
                (
                    """
                    MERGE (s:Service {name: $source})
                    SET s.last_seen_at = $updated_at
                    """,
                    {"source": source, "updated_at": timestamp},
                )
            )
            for target in targets:
                operations.extend(
                    [
                        (
                            """
                            MERGE (d:Service {name: $target})
                            SET d.last_seen_at = $updated_at
                            """,
                            {"target": target, "updated_at": timestamp},
                        ),
                        (
                            """
                            MATCH (s:Service {name: $source})
                            MATCH (d:Service {name: $target})
                            MERGE (s)-[r:DEPENDS_ON]->(d)
                            SET r.last_seen_at = $updated_at,
                                r.source = 'bootstrap'
                            """,
                            {"source": source, "target": target, "updated_at": timestamp},
                        ),
                    ]
                )
        self._execute_write_batch(operations)
        self._bootstrapped = True
        logger.info("Neo4j demo topology bootstrap completed.")

    def _relationships_from_paths(self, source: str, raw_paths: list[Any]) -> list[dict[str, str]]:
        relationships: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        pending = list(raw_paths or [])
        while pending:
            path = pending.pop(0)
            if path is None:
                continue
            if isinstance(path, list):
                pending.extend(path)
                continue
            if not hasattr(path, "nodes"):
                continue
            nodes = list(path.nodes)
            for current, nxt in zip(nodes, nodes[1:]):
                pair = (current.get("name", source), nxt.get("name", ""))
                if pair[1] and pair not in seen:
                    seen.add(pair)
                    relationships.append({"source": pair[0], "target": pair[1]})
        return relationships

    def _now_iso(self) -> str:
        return datetime.now(UTC).isoformat()

    def _json(self, value: Any) -> str:
        return json.dumps(value, sort_keys=True)
