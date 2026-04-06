export type Span = {
  span_id: string;
  parent_id?: string | null;
  service: string;
  operation: string;
  status: string;
  duration_ms: number;
  error_type?: string | null;
  metadata?: Record<string, unknown>;
};

export type LogRecord = {
  log_id: string;
  timestamp: string;
  service: string;
  level: string;
  message: string;
  logger?: string | null;
  trace_id?: string | null;
  span_id?: string | null;
  environment?: string | null;
  region?: string | null;
  tags?: Array<{ key: string; value: string }>;
  context?: Record<string, unknown>;
};

export type MetricRecord = {
  metric_id: string;
  timestamp: string;
  service: string;
  name: string;
  value: number;
  unit: string;
  aggregation?: string | null;
  source?: string | null;
  dimensions?: Record<string, string>;
};

export type AlertRecord = {
  alert_id: string;
  source: string;
  name: string;
  severity: string;
  state: string;
  service: string;
  description: string;
  triggered_at: string;
  runbook_url?: string | null;
  signal_type?: string | null;
  labels?: Record<string, string>;
};

export type ErrorRecord = {
  error_id: string;
  timestamp: string;
  service: string;
  error_class: string;
  error_message: string;
  handled: boolean;
  count: number;
  endpoint?: string | null;
  stacktrace?: string[];
  attributes?: Record<string, unknown>;
};

export type DeploymentRecord = {
  deployment_id: string;
  service: string;
  version: string;
  environment: string;
  deployed_at: string;
  commit_sha: string;
  actor: string;
  strategy: string;
  change_summary: string;
};

export type HostSignalRecord = {
  host_id: string;
  hostname: string;
  service: string;
  region: string;
  cpu_pct: number;
  memory_pct: number;
  disk_pct: number;
  network_error_rate: number;
  pod_restarts: number;
  node_status: string;
};

export type TraceRequest = {
  provider: string;
  trace_id: string;
  spans: Span[];
  logs?: LogRecord[];
  metrics?: MetricRecord[];
  alerts?: AlertRecord[];
  errors?: ErrorRecord[];
  deployments?: DeploymentRecord[];
  host_signals?: HostSignalRecord[];
  dependencies?: Array<{ source: string; target: string }>;
  environment?: string;
  tenant?: string;
  incident_hints?: string[];
};

export type FinalAnalysisResponse = {
  structured_trace: {
    trace_id: string;
    provider: string;
    root_service: string;
    root_endpoint: string;
    error_type?: string | null;
    latency_ms: number;
    call_graph: Array<Record<string, unknown>>;
    telemetry_summary?: {
      environment?: string;
      tenant?: string;
      span_count?: number;
      log_count?: number;
      metric_count?: number;
      alert_count?: number;
      error_count?: number;
      deployment_count?: number;
      host_signal_count?: number;
      impacted_services?: string[];
      critical_alerts?: Array<{ service: string; name: string; severity: string; state: string }>;
      hot_metrics?: Array<{ service: string; name: string; value: number; unit: string }>;
      incident_hints?: string[];
    };
  };
  trace_analysis: {
    failure_point: string;
    suspected_issues: string[];
    summary: string;
  };
  graph_result: {
    cypher: string;
    affected_services: string[];
    relationships: Array<{ source: string; target: string }>;
  };
  impact_analysis: {
    blast_radius: string[];
    critical_paths: string[][];
    severity: string;
    affected_services?: Array<{
      service: string;
      risk_score: number;
      level: string;
      dependency_distance?: number;
      last_incident_at?: string;
      risk_explanation?: string;
    }>;
  };
  incident_matches: Array<{
    incident_id: string;
    title: string;
    summary: string;
    root_cause: string;
    fix: string[];
    services: string[];
  }>;
  root_cause: string;
  solutions: string[];
  confidence_score: number;
  narrative?: {
    executive_summary: string;
    affected_services_overview: string;
    likely_cause_chain: string[];
    service_impacts: Array<{
      service: string;
      impact: string;
      evidence: string[];
    }>;
    recommended_actions: string[];
  };
};

export type RuntimeAffectedService = {
  service: string;
  risk_score: number;
  level: string;
  dependency_distance: number;
  impact_type: string;
  status_during_incident: string;
  risk_explanation: string;
  last_incident_at?: string | null;
};

export type RuntimeResolutionStep = {
  step: number;
  action: string;
  actor: string;
  timestamp: string;
  result: string;
  feedback?: string | null;
  notes?: string | null;
};

export type RuntimeTimelineEvent = {
  timestamp: string;
  title: string;
  detail: string;
};

export type RuntimeSimilarIncident = {
  id: string;
  resolution: string;
  similarity_score: number;
  root_cause: string;
  successful_fix: string;
};

export type RuntimeIncidentRecord = {
  id: string;
  source_trace_id?: string | null;
  title: string;
  primary_service: string;
  severity: string;
  status: string;
  affected_services_count: number;
  time_started: string;
  resolved_at?: string | null;
  resolution_duration_minutes?: number | null;
  owner_team: string;
  suspected_error: string;
  recent_deployment: string;
  alert_signals: string[];
  propagation_path: string[];
  root_cause: string;
  root_cause_service: string;
  root_cause_error_type: string;
  trigger_event: string;
  contributing_factors: string[];
  ai_explanation: string;
  affected_services: RuntimeAffectedService[];
  resolution_steps: RuntimeResolutionStep[];
  final_resolution?: string | null;
  resolved_by?: string | null;
  resolution_type?: string | null;
  post_fix_validation?: string | null;
  timeline_replay: RuntimeTimelineEvent[];
  notes?: string | null;
  confidence: number;
  recommendations: string[];
  similar_incidents: RuntimeSimilarIncident[];
};

export type IncidentStateResponse = {
  active: RuntimeIncidentRecord[];
  resolved: RuntimeIncidentRecord[];
};

export type IncidentFixRequest = {
  incident_id: string;
  action_taken: string;
  result: string;
  feedback: string;
  notes?: string;
  final_resolution: boolean;
  actor: string;
};
