from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TelemetryTag(BaseModel):
    key: str
    value: str


class Span(BaseModel):
    span_id: str
    parent_id: str | None = None
    service: str
    operation: str
    status: str = "ok"
    duration_ms: float = 0.0
    error_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LogRecord(BaseModel):
    log_id: str
    timestamp: str
    service: str
    level: str
    message: str
    logger: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    environment: str | None = None
    region: str | None = None
    tags: list[TelemetryTag] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


class MetricRecord(BaseModel):
    metric_id: str
    timestamp: str
    service: str
    name: str
    value: float
    unit: str
    aggregation: str | None = None
    source: str | None = None
    dimensions: dict[str, str] = Field(default_factory=dict)


class AlertRecord(BaseModel):
    alert_id: str
    source: str
    name: str
    severity: str
    state: str
    service: str
    description: str
    triggered_at: str
    runbook_url: str | None = None
    signal_type: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class ErrorRecord(BaseModel):
    error_id: str
    timestamp: str
    service: str
    error_class: str
    error_message: str
    handled: bool = False
    count: int = 1
    endpoint: str | None = None
    stacktrace: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class DeploymentRecord(BaseModel):
    deployment_id: str
    service: str
    version: str
    environment: str
    deployed_at: str
    commit_sha: str
    actor: str
    strategy: str
    change_summary: str


class HostSignalRecord(BaseModel):
    host_id: str
    hostname: str
    service: str
    region: str
    cpu_pct: float
    memory_pct: float
    disk_pct: float
    network_error_rate: float
    pod_restarts: int = 0
    node_status: str = "healthy"


class ServiceDependency(BaseModel):
    source: str
    target: str


class LiveTelemetrySpanEvent(BaseModel):
    name: str
    timestamp: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class LiveTelemetrySpan(BaseModel):
    trace_id: str | None = Field(default=None, alias="traceId")
    span_id: str = Field(alias="spanId")
    parent_span_id: str | None = Field(default=None, alias="parentSpanId")
    service_name: str | None = Field(default=None, alias="serviceName")
    name: str
    status: str = "ok"
    duration_ms: float | None = Field(default=None, alias="durationMs")
    start_time: str | None = Field(default=None, alias="startTime")
    end_time: str | None = Field(default=None, alias="endTime")
    attributes: dict[str, Any] = Field(default_factory=dict)
    events: list[LiveTelemetrySpanEvent] = Field(default_factory=list)


class LiveTelemetryLog(BaseModel):
    log_id: str | None = Field(default=None, alias="logId")
    timestamp: str
    service_name: str | None = Field(default=None, alias="serviceName")
    level: str
    message: str
    trace_id: str | None = Field(default=None, alias="traceId")
    span_id: str | None = Field(default=None, alias="spanId")
    logger: str | None = None
    region: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class LiveTelemetryMetric(BaseModel):
    metric_id: str | None = Field(default=None, alias="metricId")
    timestamp: str
    service_name: str | None = Field(default=None, alias="serviceName")
    name: str
    value: float
    unit: str
    aggregation: str | None = None
    source: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)


class LiveTelemetryAlert(BaseModel):
    alert_id: str | None = Field(default=None, alias="alertId")
    source: str = "opentelemetry"
    name: str
    severity: str
    state: str
    service_name: str | None = Field(default=None, alias="serviceName")
    description: str
    triggered_at: str = Field(alias="triggeredAt")
    runbook_url: str | None = Field(default=None, alias="runbookUrl")
    signal_type: str | None = Field(default=None, alias="signalType")
    labels: dict[str, str] = Field(default_factory=dict)


class LiveTelemetryRequest(BaseModel):
    provider: str = Field(default="opentelemetry", examples=["opentelemetry", "datadog", "signoz"])
    trace_id: str | None = Field(default=None, alias="traceId")
    service_name: str | None = Field(default=None, alias="serviceName")
    environment: str = "production"
    tenant: str = "rocketride"
    resource_attributes: dict[str, Any] = Field(default_factory=dict, alias="resourceAttributes")
    spans: list[LiveTelemetrySpan] = Field(default_factory=list)
    logs: list[LiveTelemetryLog] = Field(default_factory=list)
    metrics: list[LiveTelemetryMetric] = Field(default_factory=list)
    alerts: list[LiveTelemetryAlert] = Field(default_factory=list)
    incident_hints: list[str] = Field(default_factory=list, alias="incidentHints")

    model_config = {"populate_by_name": True}


class TraceIngestRequest(BaseModel):
    provider: str = Field(default="generic", examples=["datadog", "signoz"])
    trace_id: str
    spans: list[Span]
    logs: list[LogRecord] = Field(default_factory=list)
    metrics: list[MetricRecord] = Field(default_factory=list)
    alerts: list[AlertRecord] = Field(default_factory=list)
    errors: list[ErrorRecord] = Field(default_factory=list)
    deployments: list[DeploymentRecord] = Field(default_factory=list)
    host_signals: list[HostSignalRecord] = Field(default_factory=list)
    dependencies: list[ServiceDependency] = Field(default_factory=list)
    environment: str = "production"
    tenant: str = "rocketride"
    incident_hints: list[str] = Field(default_factory=list)


class StructuredTrace(BaseModel):
    trace_id: str
    provider: str
    root_service: str
    root_endpoint: str
    error_type: str | None = None
    latency_ms: float = 0.0
    call_graph: list[dict[str, Any]] = Field(default_factory=list)
    raw_spans: list[Span] = Field(default_factory=list)
    telemetry_summary: dict[str, Any] = Field(default_factory=dict)


class TraceAnalysis(BaseModel):
    failure_point: str
    suspected_issues: list[str]
    summary: str


class GraphQueryRequest(BaseModel):
    service_name: str
    question: str | None = None


class GraphQueryResult(BaseModel):
    cypher: str
    affected_services: list[str]
    relationships: list[dict[str, str]] = Field(default_factory=list)


class ImpactAnalysis(BaseModel):
    blast_radius: list[str]
    critical_paths: list[list[str]]
    severity: str


class IncidentRecord(BaseModel):
    incident_id: str
    title: str
    summary: str
    symptoms: list[str]
    root_cause: str
    fix: list[str]
    services: list[str]


class IncidentSearchResponse(BaseModel):
    query: str
    matches: list[IncidentRecord]


class ServiceImpact(BaseModel):
    service: str
    impact: str
    evidence: list[str] = Field(default_factory=list)


class AnalysisNarrative(BaseModel):
    executive_summary: str
    affected_services_overview: str
    likely_cause_chain: list[str]
    service_impacts: list[ServiceImpact] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class FinalAnalysisResponse(BaseModel):
    structured_trace: StructuredTrace
    trace_analysis: TraceAnalysis
    graph_result: GraphQueryResult
    impact_analysis: ImpactAnalysis
    incident_matches: list[IncidentRecord]
    root_cause: str
    solutions: list[str]
    confidence_score: float
    narrative: AnalysisNarrative


class RuntimeAffectedService(BaseModel):
    service: str
    risk_score: int
    level: str
    dependency_distance: int
    impact_type: str
    status_during_incident: str
    risk_explanation: str
    last_incident_at: str | None = None


class RuntimeResolutionStep(BaseModel):
    step: int
    action: str
    actor: str
    timestamp: str
    result: str
    feedback: str | None = None
    notes: str | None = None


class RuntimeTimelineEvent(BaseModel):
    timestamp: str
    title: str
    detail: str


class RuntimeSimilarIncident(BaseModel):
    id: str
    resolution: str
    similarity_score: float
    root_cause: str
    successful_fix: str


class RuntimeIncidentRecord(BaseModel):
    id: str
    title: str
    primary_service: str
    severity: str
    status: str
    affected_services_count: int
    time_started: str
    resolved_at: str | None = None
    resolution_duration_minutes: int | None = None
    owner_team: str
    suspected_error: str
    recent_deployment: str
    alert_signals: list[str] = Field(default_factory=list)
    propagation_path: list[str] = Field(default_factory=list)
    root_cause: str
    root_cause_service: str
    root_cause_error_type: str
    trigger_event: str
    contributing_factors: list[str] = Field(default_factory=list)
    ai_explanation: str
    affected_services: list[RuntimeAffectedService] = Field(default_factory=list)
    resolution_steps: list[RuntimeResolutionStep] = Field(default_factory=list)
    final_resolution: str | None = None
    resolved_by: str | None = None
    resolution_type: str | None = None
    post_fix_validation: str | None = None
    timeline_replay: list[RuntimeTimelineEvent] = Field(default_factory=list)
    notes: str | None = None
    confidence: float
    recommendations: list[str] = Field(default_factory=list)
    similar_incidents: list[RuntimeSimilarIncident] = Field(default_factory=list)


class IncidentFixRequest(BaseModel):
    incident_id: str
    action_taken: str
    result: str
    feedback: str
    notes: str | None = None
    final_resolution: bool = False
    actor: str = "operator"


class IncidentStateResponse(BaseModel):
    active: list[RuntimeIncidentRecord] = Field(default_factory=list)
    resolved: list[RuntimeIncidentRecord] = Field(default_factory=list)
