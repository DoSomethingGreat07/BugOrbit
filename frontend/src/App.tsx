import { useEffect, useState, type ReactNode } from "react";
import CytoscapeComponent from "react-cytoscapejs";
import { analyzeTrace, fetchIncidentState, recordIncidentFix } from "./services/api";
import type { FinalAnalysisResponse, RuntimeIncidentRecord, TraceRequest } from "./types/api";

type NavView =
  | "dashboard"
  | "incidents"
  | "resolved"
  | "graph"
  | "memory"
  | "telemetry"
  | "simulation"
  | "settings";

type PipelineStageId =
  | "telemetry"
  | "correlation"
  | "graph"
  | "reasoning"
  | "risk"
  | "fix"
  | "memory";

type StageStatus = "idle" | "processing" | "completed" | "error";

type PipelineStage = {
  id: PipelineStageId;
  label: string;
  detail: string;
};

type FixEntry = {
  id: string;
  incidentId: string;
  actionTaken: string;
  result: "Success" | "Failed";
  feedback: "Needs follow-up" | "Improved" | "Resolved";
  notes: string;
  finalResolution: boolean;
  timestamp: string;
};

type AffectedServiceRisk = {
  service: string;
  riskScore: number;
  level: "critical" | "high" | "medium" | "low";
  dependencyDistance: number;
  impactType: "root-cause" | "direct" | "upstream" | "downstream";
  statusDuringIncident: "degraded" | "failing" | "recovered";
  riskExplanation: string;
  lastIncidentAt?: string;
};

type ResolutionStep = {
  step: number;
  action: string;
  actor: string;
  timestamp: string;
  result: "failed" | "partial" | "success";
};

type TimelineEvent = {
  timestamp: string;
  title: string;
  detail: string;
};

type IncidentRecord = {
  id: string;
  sourceTraceId?: string;
  title: string;
  primaryService: string;
  severity: "critical" | "high" | "medium";
  status: "active" | "resolved";
  affectedServicesCount: number;
  timeStarted: string;
  resolvedAt?: string;
  resolutionDurationMinutes?: number;
  ownerTeam: string;
  suspectedError: string;
  recentDeployment: string;
  alertSignals: string[];
  propagationPath: string[];
  rootCause: string;
  rootCauseService: string;
  rootCauseErrorType: string;
  triggerEvent: string;
  contributingFactors: string[];
  aiExplanation: string;
  affectedServices: AffectedServiceRisk[];
  resolutionSteps: ResolutionStep[];
  finalResolution?: string;
  resolvedBy?: string;
  resolutionType?: string;
  postFixValidation?: string;
  timelineReplay: TimelineEvent[];
  notes?: string;
  confidence: number;
  recommendations: string[];
  similarIncidents: Array<{
    id: string;
    resolution: string;
    similarityScore: number;
    rootCause: string;
    successfulFix: string;
  }>;
};

type SimulationScenario = {
  service: string;
  failureType: string;
  predictedCascade: string[];
  expectedFixes: string[];
};

const pipelineStages: PipelineStage[] = [
  { id: "telemetry", label: "Telemetry Intake", detail: "Normalize logs, traces, alerts, and metrics." },
  { id: "correlation", label: "Signal Correlation", detail: "Cluster anomalies into an incident envelope." },
  { id: "graph", label: "Graph Mapping", detail: "Project relationships into the dependency graph." },
  { id: "reasoning", label: "AI Reasoning", detail: "Generate root-cause intelligence and evidence." },
  { id: "risk", label: "Risk Propagation", detail: "Score blast radius and cascade depth." },
  { id: "fix", label: "Fix Recommendation", detail: "Propose remediations and next best actions." },
  { id: "memory", label: "Learning Memory", detail: "Store resolution memory and similar incidents." }
];

const navItems: Array<{ id: NavView; label: string; icon: string }> = [
  { id: "dashboard", label: "Dashboard", icon: "DS" },
  { id: "incidents", label: "Live Incidents", icon: "LI" },
  { id: "resolved", label: "Resolved Incidents", icon: "RI" },
  { id: "graph", label: "Dependency Explorer", icon: "DE" },
  { id: "memory", label: "Fix Memory", icon: "FM" },
  { id: "telemetry", label: "Telemetry Explorer", icon: "TE" },
  { id: "simulation", label: "Simulation Lab", icon: "SL" },
  { id: "settings", label: "Settings", icon: "ST" }
];

const sampleTrace: TraceRequest = {
  provider: "datadog",
  trace_id: "trace-payment-telemetry-009",
  environment: "production",
  tenant: "bugorbit-enterprise",
  incident_hints: [
    "payment latency regression after canary deploy",
    "ledger database pool saturation",
    "gateway checkout timeout burst in us-central"
  ],
  spans: [
    {
      span_id: "span-001",
      service: "api-gateway",
      operation: "POST /checkout",
      status: "ok",
      duration_ms: 120,
      metadata: { route_group: "checkout", release_ring: "stable" }
    },
    {
      span_id: "span-002",
      parent_id: "span-001",
      service: "payment-service",
      operation: "authorizeCharge",
      status: "error",
      duration_ms: 960,
      error_type: "TimeoutError",
      metadata: { payment_provider: "stripe", retry_attempt: 3 }
    },
    {
      span_id: "span-003",
      parent_id: "span-002",
      service: "ledger-service",
      operation: "writeTransaction",
      status: "error",
      duration_ms: 1210,
      error_type: "PoolTimeoutException",
      metadata: { db_cluster: "ledger-primary", shard: "tx-04" }
    },
    {
      span_id: "span-004",
      parent_id: "span-002",
      service: "fraud-service",
      operation: "scorePaymentRisk",
      status: "ok",
      duration_ms: 210
    }
  ],
  logs: [
    {
      log_id: "log-001",
      timestamp: "2026-04-02T19:28:11Z",
      service: "payment-service",
      level: "ERROR",
      message: "Authorization exceeded retry budget while awaiting ledger ack",
      logger: "payments.authorizer",
      trace_id: "trace-payment-telemetry-009",
      span_id: "span-002",
      environment: "production",
      region: "us-central-1",
      tags: [
        { key: "team", value: "payments" },
        { key: "priority", value: "p1" }
      ],
      context: { retry_budget_remaining: 0, order_id: "ord-88219", customer_tier: "enterprise" }
    },
    {
      log_id: "log-002",
      timestamp: "2026-04-02T19:28:10Z",
      service: "ledger-service",
      level: "ERROR",
      message: "Connection pool exhausted for writeTransaction",
      logger: "ledger.db.pool",
      trace_id: "trace-payment-telemetry-009",
      span_id: "span-003",
      environment: "production",
      region: "us-central-1",
      tags: [
        { key: "cluster", value: "ledger-primary" },
        { key: "symptom", value: "pool-exhaustion" }
      ],
      context: { active_connections: 200, waiting_requests: 83 }
    }
  ],
  metrics: [
    {
      metric_id: "metric-001",
      timestamp: "2026-04-02T19:28:00Z",
      service: "payment-service",
      name: "payment.auth.latency.p95",
      value: 2890,
      unit: "ms",
      aggregation: "p95",
      source: "datadog",
      dimensions: { region: "us-central-1", env: "production" }
    },
    {
      metric_id: "metric-002",
      timestamp: "2026-04-02T19:28:00Z",
      service: "ledger-service",
      name: "ledger.db.connection_pool.utilization",
      value: 97,
      unit: "percent",
      aggregation: "avg",
      source: "datadog",
      dimensions: { cluster: "ledger-primary", env: "production" }
    },
    {
      metric_id: "metric-003",
      timestamp: "2026-04-02T19:28:00Z",
      service: "api-gateway",
      name: "gateway.checkout.error_rate",
      value: 18.4,
      unit: "percent",
      aggregation: "avg",
      source: "datadog",
      dimensions: { route: "/checkout", env: "production" }
    }
  ],
  alerts: [
    {
      alert_id: "alert-001",
      source: "datadog",
      name: "P1 Payment Authorization Timeout Burst",
      severity: "critical",
      state: "triggered",
      service: "payment-service",
      description: "Payment authorization timeout rate exceeded 15% for 10 minutes.",
      triggered_at: "2026-04-02T19:26:00Z",
      runbook_url: "https://runbooks.bugorbit.ai/payments/timeout-burst",
      signal_type: "apm",
      labels: { team: "payments", pager: "primary" }
    },
    {
      alert_id: "alert-002",
      source: "datadog",
      name: "Ledger DB Pool Saturation",
      severity: "critical",
      state: "triggered",
      service: "ledger-service",
      description: "Connection pool utilization has stayed above 95% for 8 minutes.",
      triggered_at: "2026-04-02T19:25:30Z",
      runbook_url: "https://runbooks.bugorbit.ai/ledger/pool-saturation",
      signal_type: "infrastructure",
      labels: { cluster: "ledger-primary", escalation: "database-sre" }
    }
  ],
  errors: [
    {
      error_id: "err-001",
      timestamp: "2026-04-02T19:28:10Z",
      service: "ledger-service",
      error_class: "PoolTimeoutException",
      error_message: "Timed out waiting for database connection from pool",
      handled: false,
      count: 84,
      endpoint: "writeTransaction",
      stacktrace: [
        "at com.bugorbit.ledger.ConnectionPool.borrow(ConnectionPool.java:188)",
        "at com.bugorbit.ledger.TransactionWriter.write(TransactionWriter.java:74)"
      ],
      attributes: { pool_name: "ledger-primary-writer", timeout_ms: 3000 }
    }
  ],
  deployments: [
    {
      deployment_id: "dep-001",
      service: "payment-service",
      version: "2026.04.02-rc3",
      environment: "production",
      deployed_at: "2026-04-02T18:55:00Z",
      commit_sha: "a91be77",
      actor: "github-actions",
      strategy: "canary",
      change_summary: "Adjusted retry strategy and auth ledger acknowledgment timeout."
    },
    {
      deployment_id: "dep-002",
      service: "ledger-service",
      version: "2026.04.02-hotfix1",
      environment: "production",
      deployed_at: "2026-04-02T17:40:00Z",
      commit_sha: "bc19df2",
      actor: "db-release-bot",
      strategy: "rolling",
      change_summary: "Increased transaction audit logging and changed pool sizing defaults."
    }
  ],
  host_signals: [
    {
      host_id: "host-001",
      hostname: "ledger-node-4",
      service: "ledger-service",
      region: "us-central-1",
      cpu_pct: 92.1,
      memory_pct: 86.4,
      disk_pct: 68.2,
      network_error_rate: 3.8,
      pod_restarts: 2,
      node_status: "degraded"
    }
  ]
};

const resolvedIncidentSeed: IncidentRecord[] = [
  {
    id: "INC-2048",
    title: "Payment authorization timeout burst",
    primaryService: "payment-service",
    severity: "critical",
    status: "resolved",
    affectedServicesCount: 9,
    timeStarted: "2026-04-02T19:26:00Z",
    resolvedAt: "2026-04-02T19:44:00Z",
    resolutionDurationMinutes: 18,
    ownerTeam: "payments",
    suspectedError: "PoolTimeoutException",
    recentDeployment: "payment-service canary v2.3",
    alertSignals: ["High Latency", "DB Timeout", "Error Spike"],
    propagationPath: [
      "ledger-service",
      "payment-service",
      "checkout-service",
      "cart-service",
      "inventory-service",
      "notification-service"
    ],
    rootCause: "The ledger database connection pool saturated after payment-service retries amplified a canary regression.",
    rootCauseService: "ledger-service",
    rootCauseErrorType: "PoolTimeoutException",
    triggerEvent: "payment-service canary deploy",
    contributingFactors: ["retry amplification", "pool saturation", "slow DB writes"],
    aiExplanation:
      "The ledger-service connection pool exhausted under retry pressure from payment-service following a canary release. Authorization requests timed out, the error propagated into checkout, and customer-facing services degraded until the canary was rolled back and pool capacity was tuned.",
    affectedServices: [
      {
        service: "ledger-service",
        riskScore: 97,
        level: "critical",
        dependencyDistance: 0,
        impactType: "root-cause",
        statusDuringIncident: "degraded",
        riskExplanation: "Root failure domain with high latency, error saturation, and database pool pressure.",
        lastIncidentAt: "2026-04-02T19:28:10Z"
      },
      {
        service: "payment-service",
        riskScore: 91,
        level: "critical",
        dependencyDistance: 1,
        impactType: "direct",
        statusDuringIncident: "failing",
        riskExplanation: "Directly inherited pool timeouts and exhausted retry budget.",
        lastIncidentAt: "2026-04-02T19:28:11Z"
      },
      {
        service: "checkout-service",
        riskScore: 84,
        level: "high",
        dependencyDistance: 2,
        impactType: "downstream",
        statusDuringIncident: "failing",
        riskExplanation: "Customer checkout requests inherited authorization timeout failures."
      },
      {
        service: "cart-service",
        riskScore: 76,
        level: "high",
        dependencyDistance: 3,
        impactType: "downstream",
        statusDuringIncident: "degraded",
        riskExplanation: "Cart transitions degraded due to checkout dependency failure."
      },
      {
        service: "inventory-service",
        riskScore: 68,
        level: "medium",
        dependencyDistance: 4,
        impactType: "downstream",
        statusDuringIncident: "degraded",
        riskExplanation: "Order finalization delays increased cache churn and stale reservations."
      },
      {
        service: "notification-service",
        riskScore: 61,
        level: "medium",
        dependencyDistance: 5,
        impactType: "downstream",
        statusDuringIncident: "degraded",
        riskExplanation: "Completion events backed up while checkout failures accumulated."
      }
    ],
    resolutionSteps: [
      {
        step: 1,
        action: "Restart payment-service pods",
        actor: "nikhil",
        timestamp: "2026-04-02T19:34:00Z",
        result: "failed"
      },
      {
        step: 2,
        action: "Increase ledger connection pool",
        actor: "database-sre",
        timestamp: "2026-04-02T19:38:00Z",
        result: "partial"
      },
      {
        step: 3,
        action: "Rollback payment-service canary",
        actor: "nikhil",
        timestamp: "2026-04-02T19:41:00Z",
        result: "success"
      }
    ],
    finalResolution: "Rolled back payment-service canary and increased ledger-service connection pool size.",
    resolvedBy: "nikhil",
    resolutionType: "Rollback + Infra tuning",
    postFixValidation: "Latency normalized, payment auth errors dropped, and checkout SLO burn stabilized.",
    timelineReplay: [
      {
        timestamp: "2026-04-02T19:26:00Z",
        title: "Canary deployment active",
        detail: "payment-service release started sending more aggressive ledger retries."
      },
      {
        timestamp: "2026-04-02T19:29:00Z",
        title: "First failure detected",
        detail: "BugOrbit correlated ledger timeout spikes with payment authorization failures."
      },
      {
        timestamp: "2026-04-02T19:33:00Z",
        title: "Graph reasoning converged",
        detail: "Dependency Explorer identified checkout, cart, and notification as cascade victims."
      },
      {
        timestamp: "2026-04-02T19:41:00Z",
        title: "Rollback applied",
        detail: "The canary release was rolled back while DB pool capacity was expanded."
      },
      {
        timestamp: "2026-04-02T19:44:00Z",
        title: "Incident resolved",
        detail: "Customer-facing latency and burn-rate alerts returned to baseline."
      }
    ],
    notes:
      "Tighten retry budgets, lower saturation alert thresholds, and gate canaries on ledger pool health.",
    confidence: 0.94,
    recommendations: ["Rollback deployment", "Increase pool capacity", "Add circuit breaker", "Tune retry budget"],
    similarIncidents: [
      {
        id: "INC-1987",
        resolution: "Rollback + pool reset",
        similarityScore: 0.91,
        rootCause: "ledger DB saturation",
        successfulFix: "rollback"
      },
      {
        id: "INC-1762",
        resolution: "Circuit breaker rollout",
        similarityScore: 0.82,
        rootCause: "retry amplification",
        successfulFix: "circuit breaker"
      }
    ]
  },
  {
    id: "INC-1987",
    title: "Ledger write saturation during settlement burst",
    primaryService: "ledger-service",
    severity: "high",
    status: "resolved",
    affectedServicesCount: 5,
    timeStarted: "2026-03-28T14:30:00Z",
    resolvedAt: "2026-03-28T14:42:00Z",
    resolutionDurationMinutes: 12,
    ownerTeam: "database-sre",
    suspectedError: "WriteSaturation",
    recentDeployment: "ledger-service hotfix1",
    alertSignals: ["Pool Saturation", "Slow Writes"],
    propagationPath: ["ledger-service", "payment-service", "api-gateway"],
    rootCause: "Settlement spikes exceeded ledger writer capacity during a compaction window.",
    rootCauseService: "ledger-service",
    rootCauseErrorType: "WriteSaturation",
    triggerEvent: "settlement workload spike",
    contributingFactors: ["compaction overlap", "under-provisioned writers"],
    aiExplanation:
      "A background compaction coincided with a settlement burst and reduced available writer capacity in ledger-service, producing queue growth and authorization latency until capacity was rebalanced.",
    affectedServices: [
      {
        service: "ledger-service",
        riskScore: 95,
        level: "critical",
        dependencyDistance: 0,
        impactType: "root-cause",
        statusDuringIncident: "degraded",
        riskExplanation: "Writer pool saturation at the origin of the incident."
      },
      {
        service: "payment-service",
        riskScore: 82,
        level: "high",
        dependencyDistance: 1,
        impactType: "direct",
        statusDuringIncident: "failing",
        riskExplanation: "Dependent authorization calls stalled behind ledger write queues."
      },
      {
        service: "api-gateway",
        riskScore: 71,
        level: "medium",
        dependencyDistance: 2,
        impactType: "upstream",
        statusDuringIncident: "degraded",
        riskExplanation: "Checkout routes inherited increased timeout rate from payment-service."
      }
    ],
    resolutionSteps: [
      {
        step: 1,
        action: "Increase writer pool size",
        actor: "database-sre",
        timestamp: "2026-03-28T14:36:00Z",
        result: "partial"
      },
      {
        step: 2,
        action: "Drain compaction workload",
        actor: "database-sre",
        timestamp: "2026-03-28T14:40:00Z",
        result: "success"
      }
    ],
    finalResolution: "Rebalanced compaction schedule and raised writer pool size.",
    resolvedBy: "database-sre",
    resolutionType: "Capacity tuning",
    postFixValidation: "Queue depth normalized and payment latency dropped under SLO.",
    timelineReplay: [
      {
        timestamp: "2026-03-28T14:30:00Z",
        title: "Writer saturation detected",
        detail: "Ledger compaction overlapped with settlement load."
      },
      {
        timestamp: "2026-03-28T14:36:00Z",
        title: "Capacity tuned",
        detail: "Writer pool and queue handling were increased."
      },
      {
        timestamp: "2026-03-28T14:42:00Z",
        title: "Recovery validated",
        detail: "Latency and error pressure returned to acceptable thresholds."
      }
    ],
    notes: "Add compaction-aware autoscaling and shift settlement windows away from compaction.",
    confidence: 0.89,
    recommendations: ["Scale writers", "Shift compaction window", "Add queue depth alert"],
    similarIncidents: [
      {
        id: "INC-2048",
        resolution: "Rollback + Infra tuning",
        similarityScore: 0.91,
        rootCause: "pool saturation",
        successfulFix: "pool expansion"
      }
    ]
  }
];

const fixMemorySeed = [
  { errorType: "PoolTimeoutException", service: "payment-service", fix: "Rollback", successRate: 92 },
  { errorType: "WriteSaturation", service: "ledger-service", fix: "Increase pool + rebalance", successRate: 88 },
  { errorType: "LatencySpike", service: "api-gateway", fix: "Route drain", successRate: 78 }
];

const initialStageState: Record<PipelineStageId, StageStatus> = {
  telemetry: "idle",
  correlation: "idle",
  graph: "idle",
  reasoning: "idle",
  risk: "idle",
  fix: "idle",
  memory: "idle"
};

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function formatDate(value: string) {
  return new Date(value).toLocaleString();
}

function statusTone(severity: string) {
  if (severity === "critical") return "critical";
  if (severity === "high") return "warning";
  return "healthy";
}

function riskLevelFromScore(score: number): AffectedServiceRisk["level"] {
  if (score >= 90) return "critical";
  if (score >= 75) return "high";
  if (score >= 60) return "medium";
  return "low";
}

function stageStatusLabel(status: StageStatus) {
  if (status === "processing") return "Processing";
  if (status === "completed") return "Completed";
  if (status === "error") return "Error";
  return "Idle";
}

function buildGraphModel(incident: IncidentRecord | null) {
  if (!incident) return { nodes: [], edges: [] } as const;

  const nodes: Array<{ id: string; label: string; type: string; x: number; y: number; subtitle?: string }> = [];
  const edges: Array<{ from: string; to: string; label: string; active?: boolean }> = [];
  const basePath = incident.propagationPath.length > 0 ? incident.propagationPath : [incident.primaryService];

  basePath.forEach((service, index) => {
    const serviceRisk = incident.affectedServices.find((item) => item.service === service);
    nodes.push({
      id: service,
      label: service,
      type:
        serviceRisk?.impactType === "root-cause"
          ? "root"
          : serviceRisk?.statusDuringIncident === "recovered"
            ? "recovered"
            : "service",
      x: 120 + index * 152,
      y: 130 + (index % 2) * 104,
      subtitle: serviceRisk ? `${serviceRisk.riskScore}%` : ""
    });
    if (index > 0) {
      edges.push({ from: basePath[index - 1], to: service, label: "IMPACTS", active: true });
    }
  });

  nodes.push({ id: `${incident.id}-incident`, label: incident.id, type: "incident", x: 60, y: 30 });
  edges.push({ from: `${incident.id}-incident`, to: incident.rootCauseService, label: "CAUSES", active: true });

  nodes.push({
    id: `${incident.id}-error`,
    label: incident.rootCauseErrorType,
    type: "error",
    x: 270,
    y: 28
  });
  edges.push({ from: incident.rootCauseService, to: `${incident.id}-error`, label: "ERROR" });

  if (incident.rootCauseService.includes("ledger")) {
    nodes.push({ id: `${incident.id}-db`, label: "ledger-db", type: "database", x: 470, y: 28 });
    edges.push({ from: incident.rootCauseService, to: `${incident.id}-db`, label: "DEPENDS_ON" });
  }

  if (incident.recentDeployment) {
    nodes.push({ id: `${incident.id}-deploy`, label: "deployment", type: "deployment", x: 640, y: 34 });
    edges.push({ from: `${incident.id}-deploy`, to: incident.primaryService, label: "TRIGGERED" });
  }

  const graphFixEntries = incident.resolutionSteps.length > 0 ? incident.resolutionSteps : [];
  graphFixEntries.slice(0, 2).forEach((entry, index) => {
    const id = `${incident.id}-fix-${index}`;
    nodes.push({
      id,
      label: entry.action,
      type: entry.result === "success" ? "fix" : "recovered",
      x: 730,
      y: 130 + index * 92
    });
    edges.push({ from: incident.primaryService, to: id, label: "RESOLVED_BY", active: entry.result === "success" });
  });

  return { nodes, edges };
}

function buildResolvedGraphModel(incident: IncidentRecord | null) {
  return buildGraphModel(incident);
}

function uniqueItems(values: Array<string | undefined | null>) {
  return [...new Set(values.filter((value): value is string => Boolean(value && value.trim())).map((value) => value.trim()))];
}

function scoreFixForFailure(fix: string, failureType: string) {
  const text = fix.toLowerCase();

  if (failureType === "DB Timeout") {
    if (/pool|connection|database|db|timeout|latency|retry|rollback/.test(text)) return 3;
    if (/restart|fail|shift traffic|circuit/.test(text)) return 2;
    return 1;
  }

  if (failureType === "Memory Leak") {
    if (/memory|heap|recycle|restart|scale|pod|replica/.test(text)) return 3;
    if (/rollback|disable|drain/.test(text)) return 2;
    return 1;
  }

  if (/latency|timeout|circuit|retry|traffic|queue|throttle/.test(text)) return 3;
  if (/rollback|restart|scale/.test(text)) return 2;
  return 1;
}

function buildSimulationScenario(
  service: string,
  failureType: string,
  result: FinalAnalysisResponse | null,
  payload: TraceRequest | null
): SimulationScenario {
  const fallbackPayload = payload ?? {
    spans: [],
    alerts: [],
    incident_hints: []
  };
  if (!result) {
    return {
      service,
      failureType,
      predictedCascade: uniqueItems([
        service,
        ...fallbackPayload.spans
          .filter((span) => span.service !== service)
          .map((span) => span.service)
          .slice(0, 4)
      ]),
      expectedFixes: uniqueItems([
        ...fallbackPayload.incident_hints ?? [],
        ...fallbackPayload.alerts?.map((alert) => alert.runbook_url ?? alert.name) ?? []
      ]).slice(0, 4)
    };
  }

  const adjacency = new Map<string, string[]>();
  const registerEdge = (from: string, to: string) => {
    adjacency.set(from, [...(adjacency.get(from) ?? []), to]);
  };

  result.graph_result.relationships.forEach(({ source, target }) => {
    registerEdge(source, target);
    registerEdge(target, source);
  });

  const queue = [service];
  const visited = new Set<string>();
  const cascade: string[] = [];

  while (queue.length > 0 && cascade.length < 6) {
    const current = queue.shift();
    if (!current || visited.has(current)) continue;
    visited.add(current);
    cascade.push(current);

    for (const neighbor of adjacency.get(current) ?? []) {
      if (!visited.has(neighbor)) queue.push(neighbor);
    }
  }

  const impactedForService = (result.impact_analysis.affected_services ?? [])
    .filter((item) => item.service === service || (item.dependency_distance ?? 99) <= 2)
    .sort((left, right) => (left.dependency_distance ?? 99) - (right.dependency_distance ?? 99))
    .map((item) => item.service);

  const graphRelated = result.graph_result.relationships.flatMap(({ source, target }) => {
    if (source === service) return [target];
    if (target === service) return [source];
    return [];
  });

  const blastRadius = result.impact_analysis.blast_radius.filter((item) => item !== result.trace_analysis.failure_point);
  const fallbackFailurePoint = result.trace_analysis.failure_point !== service ? [result.trace_analysis.failure_point] : [];

  const predictedCascade = uniqueItems([
    service,
    ...cascade.filter((item) => item !== service),
    ...impactedForService,
    ...graphRelated,
    ...fallbackFailurePoint,
    ...blastRadius
  ]).slice(0, 6);

  const expectedFixes = uniqueItems([
    ...(result.narrative?.recommended_actions ?? []),
    ...result.solutions,
    ...result.incident_matches
      .filter((incident) => incident.services.includes(service) || incident.root_cause.toLowerCase().includes(service.toLowerCase()))
      .flatMap((incident) => incident.fix),
    ...result.incident_matches.flatMap((incident) => incident.fix)
  ])
    .sort((left, right) => scoreFixForFailure(right, failureType) - scoreFixForFailure(left, failureType))
    .slice(0, 4);

  return {
    service,
    failureType,
    predictedCascade,
    expectedFixes
  };
}

function buildCurrentIncident(
  result: FinalAnalysisResponse | null,
  payload: TraceRequest | null,
  fixEntries: FixEntry[]
): IncidentRecord | null {
  if (!result || !payload) return null;

  const affectedServices = buildRiskModel(result, payload);
  const propagationPath = affectedServices.map((item) => item.service);
  const primaryService = result.trace_analysis.failure_point;
  const teamTag =
    payload.logs?.flatMap((entry) => entry.tags ?? []).find((tag) => tag.key.toLowerCase() === "team")?.value ?? "payments";

  return {
    id: result.structured_trace.trace_id,
    title: "Live incident analysis",
    primaryService,
    severity: result.impact_analysis.severity as IncidentRecord["severity"],
    status: fixEntries.some((item) => item.finalResolution) ? "resolved" : "active",
    affectedServicesCount: affectedServices.length,
    timeStarted: payload.alerts?.[0]?.triggered_at ?? new Date().toISOString(),
    resolvedAt: fixEntries.some((item) => item.finalResolution) ? new Date().toISOString() : undefined,
    resolutionDurationMinutes: fixEntries.some((item) => item.finalResolution) ? 14 : undefined,
    ownerTeam: teamTag,
    suspectedError: result.structured_trace.error_type ?? "UnknownError",
    recentDeployment: payload.deployments?.[0]
      ? `${payload.deployments[0].service} ${payload.deployments[0].version}`
      : "No deployment signal available",
    alertSignals: (payload.alerts ?? []).slice(0, 3).map((item) => item.name),
    propagationPath,
    rootCause: result.root_cause,
    rootCauseService: affectedServices[0]?.service ?? primaryService,
    rootCauseErrorType: result.structured_trace.error_type ?? "UnknownError",
    triggerEvent: payload.deployments?.[0]
      ? `${payload.deployments[0].service} ${payload.deployments[0].version} deployment`
      : "Telemetry anomaly burst",
    contributingFactors: payload.incident_hints ?? ["graph propagation", "latency amplification", "retry pressure"],
    aiExplanation: result.narrative?.executive_summary ?? result.root_cause,
    affectedServices,
    resolutionSteps: fixEntries.map((entry, index) => ({
      step: index + 1,
      action: entry.actionTaken,
      actor: "operator",
      timestamp: entry.timestamp,
      result: entry.finalResolution ? "success" : entry.result === "Failed" ? "failed" : "partial"
    })),
    finalResolution: fixEntries.find((item) => item.finalResolution)?.actionTaken,
    resolvedBy: fixEntries.find((item) => item.finalResolution) ? "operator" : undefined,
    resolutionType: fixEntries.find((item) => item.finalResolution) ? "Manual recovery" : undefined,
    postFixValidation: fixEntries.find((item) => item.finalResolution)
      ? "Signals returned to baseline and SLO burn stabilized."
      : undefined,
    timelineReplay: [
      {
        timestamp: payload.alerts?.[0]?.triggered_at ?? new Date().toISOString(),
        title: "Telemetry ingested",
        detail: "BugOrbit opened a live incident from correlated telemetry."
      },
      {
        timestamp: new Date().toISOString(),
        title: "AI reasoning completed",
        detail: result.narrative?.executive_summary ?? result.root_cause
      }
    ],
    notes: payload.incident_hints?.join(". "),
    confidence: result.confidence_score,
    recommendations: result.narrative?.recommended_actions ?? result.solutions,
    similarIncidents: result.incident_matches.map((incident) => ({
      id: incident.incident_id,
      resolution: incident.fix[0] ?? incident.root_cause,
      similarityScore: 0.82,
      rootCause: incident.root_cause,
      successfulFix: incident.fix[0] ?? "Unknown"
    }))
  };
}

function mapRuntimeIncident(incident: RuntimeIncidentRecord): IncidentRecord {
  return {
    id: incident.id,
    sourceTraceId: incident.source_trace_id ?? undefined,
    title: incident.title,
    primaryService: incident.primary_service,
    severity: incident.severity as IncidentRecord["severity"],
    status: incident.status as IncidentRecord["status"],
    affectedServicesCount: incident.affected_services_count,
    timeStarted: incident.time_started,
    resolvedAt: incident.resolved_at ?? undefined,
    resolutionDurationMinutes: incident.resolution_duration_minutes ?? undefined,
    ownerTeam: incident.owner_team,
    suspectedError: incident.suspected_error,
    recentDeployment: incident.recent_deployment,
    alertSignals: incident.alert_signals,
    propagationPath: incident.propagation_path,
    rootCause: incident.root_cause,
    rootCauseService: incident.root_cause_service,
    rootCauseErrorType: incident.root_cause_error_type,
    triggerEvent: incident.trigger_event,
    contributingFactors: incident.contributing_factors,
    aiExplanation: incident.ai_explanation,
    affectedServices: incident.affected_services.map((item) => ({
      service: item.service,
      riskScore: item.risk_score,
      level: item.level as AffectedServiceRisk["level"],
      dependencyDistance: item.dependency_distance,
      impactType: item.impact_type as AffectedServiceRisk["impactType"],
      statusDuringIncident: item.status_during_incident as AffectedServiceRisk["statusDuringIncident"],
      riskExplanation: item.risk_explanation,
      lastIncidentAt: item.last_incident_at ?? undefined
    })),
    resolutionSteps: incident.resolution_steps.map((step) => ({
      step: step.step,
      action: step.action,
      actor: step.actor,
      timestamp: step.timestamp,
      result: step.result as ResolutionStep["result"]
    })),
    finalResolution: incident.final_resolution ?? undefined,
    resolvedBy: incident.resolved_by ?? undefined,
    resolutionType: incident.resolution_type ?? undefined,
    postFixValidation: incident.post_fix_validation ?? undefined,
    timelineReplay: incident.timeline_replay,
    notes: incident.notes ?? undefined,
    confidence: incident.confidence,
    recommendations: incident.recommendations,
    similarIncidents: incident.similar_incidents.map((item) => ({
      id: item.id,
      resolution: item.resolution,
      similarityScore: item.similarity_score,
      rootCause: item.root_cause,
      successfulFix: item.successful_fix
    }))
  };
}

function buildRiskModel(result: FinalAnalysisResponse, payload: TraceRequest): AffectedServiceRisk[] {
  const explicitAffected = result.impact_analysis.affected_services;
  if (explicitAffected && explicitAffected.length > 0) {
    return [...explicitAffected]
      .map((item) => ({
        service: item.service,
        riskScore: Math.max(0, Math.min(100, Math.round(item.risk_score))),
        level: riskLevelFromScore(Math.round(item.risk_score)),
        dependencyDistance: item.dependency_distance ?? 0,
        impactType: (
          item.dependency_distance === 0
            ? "root-cause"
            : item.dependency_distance === 1
              ? "direct"
              : "downstream"
        ) as AffectedServiceRisk["impactType"],
        statusDuringIncident: (Math.round(item.risk_score) >= 75 ? "failing" : "degraded") as AffectedServiceRisk["statusDuringIncident"],
        riskExplanation:
          item.risk_explanation ??
          `Risk ${Math.round(item.risk_score)}% derived from graph depth, dependency weight, latency, and error signals.`,
        lastIncidentAt: item.last_incident_at
      }))
      .sort((left, right) => right.riskScore - left.riskScore || left.service.localeCompare(right.service));
  }

  const relatedServices = new Map<string, { service: string; distance: number }>();
  const registerService = (service: string, distance: number) => {
    const current = relatedServices.get(service);
    if (!current || distance < current.distance) relatedServices.set(service, { service, distance });
  };

  registerService(result.trace_analysis.failure_point, 0);
  result.graph_result.relationships.forEach((relationship) => {
    registerService(relationship.source, 0);
    registerService(relationship.target, 1);
  });
  result.impact_analysis.blast_radius.forEach((service, index) => registerService(service, index + 1));
  result.graph_result.affected_services.forEach((service, index) => registerService(service, index + 1));

  const serviceWeights = new Map<string, number>();
  const signalTime = new Map<string, string>();
  const addWeight = (service: string | undefined, amount: number, timestamp?: string) => {
    if (!service) return;
    serviceWeights.set(service, (serviceWeights.get(service) ?? 0) + amount);
    if (timestamp && !signalTime.has(service)) signalTime.set(service, timestamp);
  };

  for (const metric of payload.metrics ?? []) {
    const weight = /latency|error|utilization|cpu|memory/i.test(metric.name) ? Math.min(26, metric.value * 0.15) : 8;
    addWeight(metric.service, weight, metric.timestamp);
  }
  for (const alert of payload.alerts ?? []) {
    const severityWeight =
      alert.severity === "critical" ? 24 : alert.severity === "high" ? 18 : alert.severity === "medium" ? 12 : 8;
    addWeight(alert.service, severityWeight, alert.triggered_at);
  }
  for (const errorRecord of payload.errors ?? []) {
    addWeight(errorRecord.service, Math.min(22, 10 + errorRecord.count * 0.15), errorRecord.timestamp);
  }
  for (const deployment of payload.deployments ?? []) {
    addWeight(deployment.service, 8, deployment.deployed_at);
  }

  return [...relatedServices.values()]
    .map(({ service, distance }) => {
      const baseFailureWeight = distance === 0 ? 74 : 94 - distance * 10;
      const telemetryWeight = serviceWeights.get(service) ?? 0;
      const riskScore = Math.max(42, Math.min(99, Math.round(baseFailureWeight + telemetryWeight)));
      return {
        service,
        riskScore,
        level: riskLevelFromScore(riskScore),
        dependencyDistance: distance,
        impactType: distance === 0 ? "root-cause" : distance === 1 ? "direct" : "downstream",
        statusDuringIncident: riskScore >= 80 ? "failing" : riskScore >= 60 ? "degraded" : "recovered",
        riskExplanation: `${service} scored ${riskScore}% because graph depth, dependency weight, latency signals, and error pressure converged here.`,
        lastIncidentAt: signalTime.get(service)
      } satisfies AffectedServiceRisk;
    })
    .sort((left, right) => right.riskScore - left.riskScore || left.dependencyDistance - right.dependencyDistance);
}

function App() {
  const [activeView, setActiveView] = useState<NavView>("dashboard");
  const [activePipelineStage, setActivePipelineStage] = useState<PipelineStageId>("telemetry");
  const [pipelineState, setPipelineState] = useState<Record<PipelineStageId, StageStatus>>(initialStageState);
  const [traceInput, setTraceInput] = useState("");
  const [submittedTrace, setSubmittedTrace] = useState<TraceRequest | null>(null);
  const [result, setResult] = useState<FinalAnalysisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedService, setSelectedService] = useState("ledger-service");
  const [selectedResolvedId, setSelectedResolvedId] = useState("");
  const [selectedLiveIncidentId, setSelectedLiveIncidentId] = useState("");
  const [resolvedSearch, setResolvedSearch] = useState("");
  const [resolvedSeverityFilter, setResolvedSeverityFilter] = useState("all");
  const [resolvedResolutionTypeFilter, setResolvedResolutionTypeFilter] = useState("all");
  const [resolvedTeamFilter, setResolvedTeamFilter] = useState("all");
  const [resolvedSort, setResolvedSort] = useState("recent");
  const [telemetryView, setTelemetryView] = useState<"logs" | "metrics" | "alerts" | "traces">("logs");
  const [edgeFilter, setEdgeFilter] = useState("All edges");
  const [graphZoom, setGraphZoom] = useState(1);
  const [simulationService, setSimulationService] = useState("ledger-service");
  const [simulationFailure, setSimulationFailure] = useState("DB Timeout");
  const [simulationRun, setSimulationRun] = useState<SimulationScenario | null>(null);
  const [activeIncidentRecords, setActiveIncidentRecords] = useState<IncidentRecord[]>([]);
  const [resolvedIncidentRecords, setResolvedIncidentRecords] = useState<IncidentRecord[]>([]);
  const [incidentStateError, setIncidentStateError] = useState<string | null>(null);
  const [demoMode, setDemoMode] = useState(false);
  const [fixSubmitError, setFixSubmitError] = useState<string | null>(null);
  const [fixSubmitSuccess, setFixSubmitSuccess] = useState<string | null>(null);
  const [fixSubmitting, setFixSubmitting] = useState(false);
  const [fixForm, setFixForm] = useState({
    incidentId: "",
    actionTaken: "",
    result: "Success" as FixEntry["result"],
    feedback: "Improved" as FixEntry["feedback"],
    notes: "",
    finalResolution: false
  });
  const [fixEntries, setFixEntries] = useState<FixEntry[]>([]);
  const [collapsedSections, setCollapsedSections] = useState({
    summary: false,
    risk: false,
    fixes: false,
    entry: false,
    memory: false
  });

  const currentIncidentId = result?.structured_trace.trace_id ?? "";
  const currentIncidentFixEntries = fixEntries.filter((entry) => entry.incidentId === currentIncidentId);
  const localCurrentIncident = buildCurrentIncident(result, submittedTrace, currentIncidentFixEntries);
  const currentIncident =
    activeIncidentRecords.find((incident) => incident.sourceTraceId === currentIncidentId) ??
    resolvedIncidentRecords.find((incident) => incident.sourceTraceId === currentIncidentId) ??
    localCurrentIncident;
  const dashboardIncident = result && submittedTrace ? currentIncident : null;
  const resolvedIncidents = resolvedIncidentRecords;
  const selectedResolvedIncident =
    resolvedIncidents.find((incident) => incident.id === selectedResolvedId) ?? resolvedIncidents[0] ?? null;
  const activeIncidents = activeIncidentRecords;
  const selectedLiveIncident =
    activeIncidents.find((incident) => incident.id === selectedLiveIncidentId) ??
    activeIncidents.find((incident) => incident.sourceTraceId === currentIncidentId) ??
    activeIncidents[0] ??
    currentIncident;
  const displayedIncident = activeView === "resolved" ? selectedResolvedIncident : selectedLiveIncident;
  const systemStatus = displayedIncident ? statusTone(displayedIncident.severity) : "healthy";
  const allIncidents = [...activeIncidents, ...resolvedIncidents];
  const filteredLiveIncidents = activeIncidents.filter((incident) => {
    const query = searchTerm.trim().toLowerCase();
    if (!query) return true;
    return [incident.id, incident.primaryService, incident.suspectedError].some((value) =>
      value.toLowerCase().includes(query)
    );
  });
  const filteredResolvedIncidents = resolvedIncidents
    .filter((incident) => {
      const query = resolvedSearch.trim().toLowerCase();
      const matchesQuery =
        !query ||
        [
          incident.id,
          incident.primaryService,
          incident.suspectedError,
          incident.ownerTeam,
          incident.rootCauseErrorType
        ].some((value) => value.toLowerCase().includes(query));
      const matchesSeverity = resolvedSeverityFilter === "all" || incident.severity === resolvedSeverityFilter;
      const matchesResolutionType =
        resolvedResolutionTypeFilter === "all" || (incident.resolutionType ?? "unknown") === resolvedResolutionTypeFilter;
      const matchesTeam = resolvedTeamFilter === "all" || incident.ownerTeam === resolvedTeamFilter;
      return matchesQuery && matchesSeverity && matchesResolutionType && matchesTeam;
    })
    .sort((left, right) => {
      if (resolvedSort === "longest") {
        return (right.resolutionDurationMinutes ?? 0) - (left.resolutionDurationMinutes ?? 0);
      }
      if (resolvedSort === "severity") {
        const score = { critical: 3, high: 2, medium: 1 };
        return score[right.severity] - score[left.severity];
      }
      return new Date(right.resolvedAt ?? right.timeStarted).getTime() - new Date(left.resolvedAt ?? left.timeStarted).getTime();
    });
  const resolvedOverview = {
    averageResolutionTime:
      resolvedIncidents.length > 0
        ? Math.round(
            resolvedIncidents.reduce((total, incident) => total + (incident.resolutionDurationMinutes ?? 0), 0) /
              resolvedIncidents.length
          )
        : 0,
    incidentsThisWeek: resolvedIncidents.filter((incident) => {
      return Date.now() - new Date(incident.resolvedAt ?? incident.timeStarted).getTime() < 7 * 24 * 60 * 60 * 1000;
    }).length
  };
  const simulationServiceOptions = uniqueItems([
    simulationService,
    result?.trace_analysis.failure_point,
    ...(submittedTrace?.spans.map((span) => span.service) ?? []),
    ...result?.graph_result.affected_services ?? [],
    ...result?.impact_analysis.blast_radius ?? []
  ]);
  const liveIncidentOptions = activeIncidents.length > 0 ? activeIncidents : currentIncident ? [currentIncident] : [];
  const scopedFixEntries =
    displayedIncident ? fixEntries.filter((entry) => entry.incidentId === displayedIncident.id) : fixEntries;

  useEffect(() => {
    if (!simulationRun) return;
    setSimulationRun(buildSimulationScenario(simulationService, simulationFailure, result, submittedTrace));
  }, [simulationService, simulationFailure, result, submittedTrace]);

  async function refreshIncidentState() {
    const snapshot = await fetchIncidentState();
    setIncidentStateError(null);
    setActiveIncidentRecords(snapshot.active.map(mapRuntimeIncident));
    setResolvedIncidentRecords(snapshot.resolved.map(mapRuntimeIncident));
    if (snapshot.resolved.length > 0 && !snapshot.resolved.some((incident) => incident.id === selectedResolvedId)) {
      setSelectedResolvedId(snapshot.resolved[0].id);
    }
  }

  async function refreshIncidentStateSafely() {
    try {
      await refreshIncidentState();
    } catch (caughtError) {
      const message =
        caughtError instanceof Error ? caughtError.message : "Unable to refresh live incident state from the backend.";
      setIncidentStateError(`${message} Dashboard analysis can still render locally, but Live and Resolved incident views may be out of date.`);
    }
  }

  useEffect(() => {
    refreshIncidentStateSafely();
  }, []);

  useEffect(() => {
    if (fixForm.incidentId) return;
    if (!currentIncidentId) return;
    setFixForm((current) => ({ ...current, incidentId: currentIncidentId }));
  }, [currentIncidentId, fixForm.incidentId]);

  useEffect(() => {
    if (resolvedIncidents.some((incident) => incident.id === selectedResolvedId)) return;
    if (resolvedIncidents[0]) setSelectedResolvedId(resolvedIncidents[0].id);
  }, [resolvedIncidents, selectedResolvedId]);

  useEffect(() => {
    if (activeIncidents.some((incident) => incident.id === selectedLiveIncidentId)) return;
    const preferredIncident =
      activeIncidents.find((incident) => incident.sourceTraceId === currentIncidentId) ?? activeIncidents[0] ?? null;
    setSelectedLiveIncidentId(preferredIncident?.id ?? "");
  }, [activeIncidents, currentIncidentId, selectedLiveIncidentId]);

  async function runPipelineAnalysis(payload: TraceRequest, nextView: NavView) {
    setLoading(true);
    setError(null);
    setSubmittedTrace(payload);
    setTraceInput(JSON.stringify(payload, null, 2));
    setPipelineState(initialStageState);
    setActivePipelineStage("telemetry");

    try {
      const sequence = pipelineStages.map((stage) => stage.id);

      setPipelineState((current) => ({ ...current, telemetry: "processing" }));
      await sleep(220);
      setPipelineState((current) => ({ ...current, telemetry: "completed", correlation: "processing" }));
      setActivePipelineStage("correlation");
      await sleep(220);
      setPipelineState((current) => ({ ...current, correlation: "completed", graph: "processing" }));
      setActivePipelineStage("graph");

      const analysis = await analyzeTrace(payload);
      setResult(analysis);
      setSelectedService(analysis.trace_analysis.failure_point);
      setSimulationService(analysis.trace_analysis.failure_point);

      for (let index = 3; index < sequence.length; index += 1) {
        const previous = sequence[index - 1];
        const current = sequence[index];
        setPipelineState((state) => ({ ...state, [previous]: "completed", [current]: "processing" }));
        setActivePipelineStage(current);
        await sleep(220);
      }

      setPipelineState({
        telemetry: "completed",
        correlation: "completed",
        graph: "completed",
        reasoning: "completed",
        risk: "completed",
        fix: "completed",
        memory: "completed"
      });
      setActivePipelineStage("memory");
      await refreshIncidentStateSafely();
      setActiveView(nextView);
      return analysis;
    } catch (caughtError) {
      const message = caughtError instanceof Error ? caughtError.message : "Unable to analyze telemetry.";
      setError(message);
      setPipelineState((current) => ({
        ...current,
        [activePipelineStage]: "error"
      }));
    } finally {
      setLoading(false);
    }

    return null;
  }

  async function handleAnalyze() {
    if (!traceInput.trim()) {
      setError("Paste a telemetry payload before running analysis.");
      return;
    }
    const payload = JSON.parse(traceInput) as TraceRequest;
    await runPipelineAnalysis(payload, "dashboard");
  }

  async function handleDemoMode() {
    setDemoMode(true);
    const analysis = await runPipelineAnalysis(sampleTrace, "dashboard");
    setSimulationRun(buildSimulationScenario("ledger-service", "DB Timeout", analysis, sampleTrace));
  }

  async function submitFixEntry() {
    if (!fixForm.incidentId || !fixForm.actionTaken.trim()) return;
    setFixSubmitError(null);
    setFixSubmitSuccess(null);
    setFixSubmitting(true);
    const entry: FixEntry = {
      id: `fix-${Date.now()}`,
      incidentId: fixForm.incidentId,
      actionTaken: fixForm.actionTaken.trim(),
      result: fixForm.result,
      feedback: fixForm.feedback,
      notes: fixForm.notes.trim(),
      finalResolution: fixForm.finalResolution,
      timestamp: new Date().toISOString()
    };
    try {
      await recordIncidentFix({
        incident_id: fixForm.incidentId,
        action_taken: entry.actionTaken,
        result: entry.result,
        feedback: entry.feedback,
        notes: entry.notes,
        final_resolution: entry.finalResolution,
        actor: "operator"
      });
      setFixSubmitSuccess(
        entry.finalResolution
          ? `Fix recorded and incident ${entry.incidentId} moved to resolved.`
          : `Fix step recorded for incident ${entry.incidentId}.`
      );
    } catch (caughtError) {
      const message = caughtError instanceof Error ? caughtError.message : "Unable to sync fix with backend.";
      setFixSubmitError(`${message} Saved locally in the UI only.`);
      setFixSubmitSuccess(`Fix step saved locally for incident ${entry.incidentId}.`);
    } finally {
      setFixEntries((current) => [...current, entry]);
      await refreshIncidentStateSafely();
      if (entry.finalResolution) {
        setSelectedResolvedId(entry.incidentId);
        setActiveView("resolved");
      }
      setFixForm({
        incidentId: fixForm.incidentId,
        actionTaken: "",
        result: "Success",
        feedback: "Improved",
        notes: "",
        finalResolution: false
      });
      setFixSubmitting(false);
    }
  }

  function toggleSection(section: keyof typeof collapsedSections) {
    setCollapsedSections((current) => ({ ...current, [section]: !current[section] }));
  }

  function renderPipeline() {
    return (
      <section className="mission-pipeline">
        <div className="mission-pipeline__header">
          <div>
            <p className="eyebrow">Incident Flow Pipeline</p>
            <h2>Telemetry to learning lifecycle</h2>
          </div>
          <div className="mission-pipeline__status">
            <span className={`status-pill status-pill--${loading ? "processing" : error ? "error" : "ready"}`}>
              {loading ? "Pipeline running" : error ? "Pipeline error" : "Ready"}
            </span>
          </div>
        </div>
        <div className="pipeline-track">
          {pipelineStages.map((stage, index) => (
            <div className="pipeline-track__segment" key={stage.id}>
              <button
                type="button"
                className={`pipeline-stage pipeline-stage--${pipelineState[stage.id]} ${
                  activePipelineStage === stage.id ? "is-active" : ""
                }`}
                onClick={() => setActivePipelineStage(stage.id)}
              >
                <span className="pipeline-stage__index">0{index + 1}</span>
                <strong>{stage.label}</strong>
                <small>{stageStatusLabel(pipelineState[stage.id])}</small>
              </button>
              {index < pipelineStages.length - 1 ? (
                <div className={`pipeline-connector pipeline-connector--${pipelineState[stage.id]}`} />
              ) : null}
            </div>
          ))}
        </div>
        <div className="pipeline-stage-detail">
          <strong>{pipelineStages.find((stage) => stage.id === activePipelineStage)?.label}</strong>
          <p>{pipelineStages.find((stage) => stage.id === activePipelineStage)?.detail}</p>
        </div>
      </section>
    );
  }

  function renderGraphCanvas(model: ReturnType<typeof buildGraphModel>) {
    if (model.nodes.length === 0) {
      return <p className="muted">Run incident analysis to project a live graph.</p>;
    }

    const elements = [
      ...model.nodes.map((node) => ({
        data: { id: node.id, label: node.label, subtitle: node.subtitle, type: node.type },
        position: { x: node.x, y: node.y },
      })),
      ...model.edges
        .filter((edge) => edgeFilter === "All edges" || edge.label === edgeFilter)
        .map((edge) => ({
          data: { source: edge.from, target: edge.to, label: edge.label, active: edge.active },
        })),
    ];

    const stylesheet: any = [
      {
        selector: "node",
        style: {
          label: "data(label)",
          "background-color": "#1a293b",
          color: "#f0f4f8",
          shape: "round-rectangle",
          width: 132,
          height: 56,
          "text-valign": "center",
          "text-halign": "center",
          "border-width": 2,
          "border-color": "rgba(255, 255, 255, 0.1)",
          "font-size": "12px",
        },
      },
      {
        selector: 'node[type = "service"]',
        style: {
          "border-color": "#41b6ff",
        },
      },
      {
        selector: 'node[type = "infrastructure"]',
        style: {
          "border-color": "#ff5252",
        },
      },
      {
        selector: "edge",
        style: {
          width: 2.5,
          "line-color": "rgba(179, 196, 219, 0.34)",
          "target-arrow-color": "rgba(179, 196, 219, 0.34)",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
          label: "data(label)",
          "font-size": "10px",
          color: "#9baec4",
          "text-background-opacity": 1,
          "text-background-color": "#061018",
        },
      },
      {
        selector: "edge[?active]",
        style: {
          "line-color": "#ff5252",
          "target-arrow-color": "#ff5252",
          color: "#ff5252",
        },
      },
    ];

    return (
      <div className="graph-shell" style={{ width: "100%", height: "420px", overflow: "hidden" }}>
        <CytoscapeComponent
          elements={elements as any}
          style={{ width: "100%", height: "100%" }}
          stylesheet={stylesheet}
          layout={{ name: "preset" }}
          cy={(cy) => {
            cy.on("tap", "node", (evt) => {
              const node = evt.target;
              setSelectedService(node.data("label"));
            });
          }}
        />
      </div>
    );
  }

  function renderSystemOverviewLayer() {
    const meanTimeToResolution = resolvedOverview.averageResolutionTime;
    const meanTimeToDetection = 6;
    const hasSubmittedPayload = Boolean(submittedTrace && result);
    return (
      <section className="mission-layer">
        <div className="mission-layer__header">
          <div>
            <p className="eyebrow">Layer 1</p>
            <h2>System Overview</h2>
          </div>
          <span className="layer-tag">Mission Control</span>
        </div>
        <div className="overview-grid">
          {[
            {
              label: "Total Services",
              value: hasSubmittedPayload ? new Set((submittedTrace?.spans ?? []).map((span) => span.service)).size : 0,
              trend: "+3%",
              meta: `MTTD ${meanTimeToDetection}m`
            },
            {
              label: "Active Incidents",
              value: hasSubmittedPayload ? activeIncidents.length : 0,
              trend: hasSubmittedPayload && activeIncidents.length > 0 ? "+1" : "0",
              meta: hasSubmittedPayload ? `Search scope ${allIncidents.length}` : "Analyze telemetry to populate"
            },
            {
              label: "Resolved Incidents",
              value: hasSubmittedPayload ? resolvedIncidents.length : 0,
              trend: "+2 this week",
              meta: hasSubmittedPayload ? `MTTR ${meanTimeToResolution}m` : "No session data yet"
            },
            {
              label: "High-Risk Services",
              value: dashboardIncident?.affectedServices.filter((service) => service.riskScore >= 75).length ?? 0,
              trend: dashboardIncident ? "-1" : "0",
              meta: hasSubmittedPayload ? "Risk score descending" : "Awaiting analysis"
            },
            {
              label: "Recent Deployments",
              value: submittedTrace?.deployments?.length ?? 0,
              trend: "+canary",
              meta: hasSubmittedPayload ? "Last 24 hours" : "No payload submitted"
            }
          ].map((card) => (
            <article className="overview-card" key={card.label}>
              <span>{card.label}</span>
              <strong>{card.value}</strong>
              <div className="sparkline">
                <i />
                <i />
                <i />
                <i />
              </div>
              <small>
                {card.trend} · {card.meta}
              </small>
            </article>
          ))}
        </div>
      </section>
    );
  }

  function renderTelemetryLayer() {
    const hasTelemetry = Boolean(submittedTrace);
    const telemetry = submittedTrace;
    return (
      <section className="mission-layer">
        <div className="mission-layer__header">
          <div>
            <p className="eyebrow">Layer 2</p>
            <h2>Telemetry Intake</h2>
          </div>
          <span className="layer-tag">Structured stream</span>
        </div>
        <div className="layer-grid layer-grid--2">
          <article className="panel-card">
            <div className="panel-card__header">
              <div>
                <h3>Telemetry Stream</h3>
                <p>Paste, upload, or replay telemetry and let BugOrbit animate the lifecycle.</p>
              </div>
              <div className="button-row">
                <button type="button" className="primary-button" onClick={() => {
                  setTraceInput(JSON.stringify(sampleTrace, null, 2));
                  runPipelineAnalysis(sampleTrace, "dashboard");
                }} disabled={loading}>
                  {loading ? "Analyzing..." : "Load and Analyze Payload"}
                </button>
                <button type="button" className="ghost-button" onClick={handleAnalyze} disabled={loading || !traceInput.trim()}>
                  Run Current Payload
                </button>
              </div>
            </div>
            <div className="stream-badges">
              <span className="stream-badge">Logs</span>
              <span className="stream-badge">Metrics</span>
              <span className="stream-badge">Alerts</span>
              <span className="stream-badge">Traces</span>
              <span className="stream-badge stream-badge--pulse">Anomalies detected</span>
            </div>
            <textarea value={traceInput} onChange={(event) => setTraceInput(event.target.value)} spellCheck={false} />
          </article>
          <article className="panel-card">
            <div className="panel-card__header">
              <div>
                <h3>Stream Views</h3>
                <p>Inspect the extracted signals feeding the BugOrbit mission pipeline.</p>
              </div>
            </div>
            <div className="segmented-control">
              {(["logs", "metrics", "alerts", "traces"] as const).map((view) => (
                <button
                  type="button"
                  key={view}
                  className={telemetryView === view ? "is-active" : ""}
                  onClick={() => setTelemetryView(view)}
                >
                  {view}
                </button>
              ))}
            </div>
            <div className="signal-feed">
              {!hasTelemetry ? <p className="muted">No payload submitted yet. Paste telemetry JSON and run analysis.</p> : null}
              {hasTelemetry && telemetryView === "logs" &&
                (telemetry?.logs ?? []).map((entry) => (
                  <div className="signal-feed__row" key={entry.log_id}>
                    <strong>{entry.service}</strong>
                    <span>{entry.message}</span>
                  </div>
                ))}
              {hasTelemetry && telemetryView === "metrics" &&
                (telemetry?.metrics ?? []).map((metric) => (
                  <div className="metric-row" key={metric.metric_id}>
                    <div>
                      <strong>{metric.name}</strong>
                      <span>{metric.service}</span>
                    </div>
                    <div className="risk-meter">
                      <div style={{ width: `${Math.min(metric.value, 100)}%` }} />
                    </div>
                  </div>
                ))}
              {hasTelemetry && telemetryView === "alerts" &&
                (telemetry?.alerts ?? []).map((alert) => (
                  <div className="signal-feed__row" key={alert.alert_id}>
                    <strong>{alert.name}</strong>
                    <span>{formatDate(alert.triggered_at)}</span>
                  </div>
                ))}
              {hasTelemetry && telemetryView === "traces" &&
                (telemetry?.spans ?? []).map((span) => (
                  <div className="signal-feed__row" key={span.span_id}>
                    <strong>{span.service}</strong>
                    <span>{span.operation}</span>
                  </div>
                ))}
            </div>
          </article>
        </div>
      </section>
    );
  }

  function renderGraphLayer() {
    return (
      <section className="mission-layer">
        <div className="mission-layer__header">
          <div>
            <p className="eyebrow">Layer 3</p>
            <h2>Graph Mapping</h2>
          </div>
          <span className="layer-tag">Neo4j layer</span>
        </div>
        <div className="layer-grid layer-grid--2">
          <article className="panel-card panel-card--wide">
            <div className="panel-card__header">
              <div>
                <h3>Dependency Explorer</h3>
                <p>Project services, databases, incidents, deployments, and fixes into the graph.</p>
              </div>
            </div>
            {renderGraphCanvas(buildGraphModel(displayedIncident))}
          </article>
          <article className="panel-card">
            <div className="panel-card__header">
              <div>
                <h3>Node Metadata</h3>
                <p>Hover and click through the graph to inspect service state.</p>
              </div>
            </div>
            <div className="metadata-stack">
              <div className="detail-chip">
                <span>Selected Service</span>
                <strong>{selectedService}</strong>
              </div>
              <div className="detail-chip">
                <span>Recent Incidents</span>
                <strong>{allIncidents.filter((incident) => incident.propagationPath.includes(selectedService)).length}</strong>
              </div>
              <div className="detail-chip">
                <span>Blast Radius</span>
                <strong>{displayedIncident?.affectedServicesCount ?? 0}</strong>
              </div>
              <div className="chip-cluster">
                {(displayedIncident?.propagationPath ?? []).map((service) => (
                  <button type="button" key={service} className="service-chip" onClick={() => setSelectedService(service)}>
                    {service}
                  </button>
                ))}
              </div>
            </div>
          </article>
        </div>
      </section>
    );
  }

  function renderReasoningLayer() {
    return (
      <section className="mission-layer">
        <div className="mission-layer__header">
          <div>
            <p className="eyebrow">Layer 4</p>
            <h2>AI Root Cause Intelligence</h2>
          </div>
          <span className="layer-tag">RocketRide reasoning</span>
        </div>
        <div className="layer-grid layer-grid--2">
          <article className="panel-card">
            <div className="panel-card__header">
              <div>
                <h3>Root Cause</h3>
                <p>{displayedIncident?.rootCause ?? "Run analysis to generate AI reasoning."}</p>
              </div>
            </div>
            {displayedIncident ? (
              <>
                <div className="confidence-card">
                  <span>Confidence</span>
                  <strong>{Math.round(displayedIncident.confidence * 100)}%</strong>
                  <div className="confidence-bar">
                    <div style={{ width: `${Math.round(displayedIncident.confidence * 100)}%` }} />
                  </div>
                </div>
                <div className="detail-grid">
                  <div className="detail-chip">
                    <span>Root Cause Service</span>
                    <strong>{displayedIncident.rootCauseService}</strong>
                  </div>
                  <div className="detail-chip">
                    <span>Error Type</span>
                    <strong>{displayedIncident.rootCauseErrorType}</strong>
                  </div>
                  <div className="detail-chip">
                    <span>Trigger Event</span>
                    <strong>{displayedIncident.triggerEvent}</strong>
                  </div>
                  <div className="detail-chip">
                    <span>Evidence Signals</span>
                    <strong>{displayedIncident.alertSignals.join(", ")}</strong>
                  </div>
                </div>
              </>
            ) : (
              <p className="muted">No reasoning available yet.</p>
            )}
          </article>
          <article className="panel-card">
            <div className="panel-card__header">
              <div>
                <h3>Reasoning Summary</h3>
                <p>Explainable AI summary showing why the failure was isolated.</p>
              </div>
            </div>
            <div className="explanation-card">
              <p>{displayedIncident?.aiExplanation ?? "Awaiting telemetry analysis."}</p>
            </div>
            <div className="tag-list">
              {(displayedIncident?.contributingFactors ?? []).map((factor) => (
                <span key={factor} className="history-pill">
                  {factor}
                </span>
              ))}
            </div>
          </article>
        </div>
      </section>
    );
  }

  function renderRiskLayer() {
    const services = displayedIncident?.affectedServices ?? [];
    return (
      <section className="mission-layer">
        <div className="mission-layer__header">
          <div>
            <p className="eyebrow">Layer 5</p>
            <h2>Risk Propagation</h2>
          </div>
          <span className="layer-tag">Ordered cascade</span>
        </div>
        <div className="layer-grid layer-grid--2">
          <article className="panel-card panel-card--wide">
            <div className="panel-card__header">
              <div>
                <h3>Ordered Risk Table</h3>
                <p>Every service list, path, and graph highlight uses the same sorted risk model.</p>
              </div>
            </div>
            <div className="risk-table">
              <div className="risk-table__head">
                <span>Service</span>
                <span>Risk</span>
                <span>Impact</span>
                <span>Hop</span>
              </div>
              {services.map((service) => (
                <button
                  type="button"
                  key={service.service}
                  className={`risk-table__row risk-table__row--${service.level}`}
                  onClick={() => setSelectedService(service.service)}
                  title={`${service.riskExplanation}${service.lastIncidentAt ? ` Last incident ${formatDate(service.lastIncidentAt)}.` : ""}`}
                >
                  <span>{service.service}</span>
                  <span>
                    <div className="risk-meter">
                      <div className={`risk-meter__fill risk-meter__fill--${service.level}`} style={{ width: `${service.riskScore}%` }} />
                    </div>
                    {service.riskScore}%
                  </span>
                  <span>{service.impactType}</span>
                  <span>{service.dependencyDistance === 0 ? "root" : service.dependencyDistance}</span>
                </button>
              ))}
            </div>
          </article>
          <article className="panel-card">
            <div className="panel-card__header">
              <div>
                <h3>Propagation Path</h3>
                <p>BugOrbit keeps path ordering consistent across graph, table, and intelligence views.</p>
              </div>
            </div>
            <div className="propagation-list">
              {services.map((service, index) => (
                <div className="propagation-step" key={service.service}>
                  <strong>{index + 1}</strong>
                  <span>{service.service}</span>
                </div>
              ))}
            </div>
          </article>
        </div>
      </section>
    );
  }

  function renderFixLayer() {
    return (
      <section className="mission-layer">
        <div className="mission-layer__header">
          <div>
            <p className="eyebrow">Layer 6</p>
            <h2>Fix Action Engine</h2>
          </div>
          <span className="layer-tag">Resolution workflow</span>
        </div>
        <div className="layer-grid layer-grid--2">
          <article className="panel-card">
            <div className="panel-card__header">
              <div>
                <h3>Recommended Fixes</h3>
                <p>Guided remediation with manual action logging and auto-fix simulation.</p>
              </div>
            </div>
            <ol className="fix-recommendations">
              {(displayedIncident?.recommendations ?? ["Run BugOrbit analysis to surface recommended fixes."]).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ol>
            <div className="step-tracker">
              {(scopedFixEntries.length > 0 ? scopedFixEntries : displayedIncident?.resolutionSteps ?? []).map((entry, index) => (
                <div className="step-chip" key={`step-${index}`}>
                  <span>Step {index + 1}</span>
                  <strong>{"actionTaken" in entry ? entry.actionTaken : entry.action}</strong>
                </div>
              ))}
            </div>
          </article>
          <article className="panel-card">
            <div className="panel-card__header">
              <div>
                <h3>Manual Fix Input</h3>
                <p>Capture operator actions and build the resolution timeline.</p>
              </div>
            </div>
            {fixSubmitSuccess ? <div className="success-banner">{fixSubmitSuccess}</div> : null}
            {fixSubmitError ? <div className="error-banner">{fixSubmitError}</div> : null}
            <div className="form-grid">
              <label>
                Live Incident
                <select
                  value={fixForm.incidentId}
                  onChange={(event) => setFixForm((current) => ({ ...current, incidentId: event.target.value }))}
                >
                  {liveIncidentOptions.length === 0 ? (
                    <option value="">No live incidents available</option>
                  ) : (
                    liveIncidentOptions.map((incident) => (
                      <option key={incident.id} value={incident.id}>
                        {incident.id} · {incident.primaryService} · {incident.severity}
                      </option>
                    ))
                  )}
                </select>
              </label>
              <label>
                Action Taken
                <input
                  value={fixForm.actionTaken}
                  onChange={(event) => setFixForm((current) => ({ ...current, actionTaken: event.target.value }))}
                />
              </label>
              <label>
                Result
                <select
                  value={fixForm.result}
                  onChange={(event) =>
                    setFixForm((current) => ({ ...current, result: event.target.value as FixEntry["result"] }))
                  }
                >
                  <option value="Success">Success</option>
                  <option value="Failed">Failed</option>
                </select>
              </label>
              <label>
                Feedback
                <select
                  value={fixForm.feedback}
                  onChange={(event) =>
                    setFixForm((current) => ({ ...current, feedback: event.target.value as FixEntry["feedback"] }))
                  }
                >
                  <option value="Improved">Improved</option>
                  <option value="Resolved">Resolved</option>
                  <option value="Needs follow-up">Needs follow-up</option>
                </select>
              </label>
              <label>
                Notes
                <textarea
                  value={fixForm.notes}
                  onChange={(event) => setFixForm((current) => ({ ...current, notes: event.target.value }))}
                />
              </label>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={fixForm.finalResolution}
                  onChange={(event) => setFixForm((current) => ({ ...current, finalResolution: event.target.checked }))}
                />
                Final Resolution Toggle
              </label>
              <button
                type="button"
                className="primary-button"
                onClick={submitFixEntry}
                disabled={liveIncidentOptions.length === 0 || fixSubmitting}
              >
                {fixSubmitting ? "Recording..." : "Record Fix"}
              </button>
            </div>
          </article>
        </div>
      </section>
    );
  }

  function renderLearningLayer() {
    return (
      <section className="mission-layer">
        <div className="mission-layer__header">
          <div>
            <p className="eyebrow">Layer 7</p>
            <h2>Incident Memory Engine</h2>
          </div>
          <span className="layer-tag">Learning loop</span>
        </div>
        <div className="layer-grid layer-grid--2">
          <article className="panel-card">
            <div className="panel-card__header">
              <div>
                <h3>Stored Memory</h3>
                <p>BugOrbit links incident, fix, and success outcomes for future investigations.</p>
              </div>
            </div>
            <div className="memory-timeline">
              {resolvedIncidents.map((incident) => (
                <button
                  type="button"
                  key={incident.id}
                  className="memory-card"
                  onClick={() => {
                    setSelectedResolvedId(incident.id);
                    setActiveView("resolved");
                  }}
                >
                  <strong>{incident.id}</strong>
                  <p>{incident.finalResolution}</p>
                  <small>{incident.resolutionType}</small>
                </button>
              ))}
            </div>
          </article>
          <article className="panel-card">
            <div className="panel-card__header">
              <div>
                <h3>Similarity Matches</h3>
                <p>Replay comparable incidents and compare successful fix paths.</p>
              </div>
            </div>
            <div className="similar-grid">
              {(displayedIncident?.similarIncidents ?? []).map((item) => (
                <button type="button" className="history-card" key={item.id} onClick={() => setActiveView("resolved")}>
                  <div>
                    <strong>{item.id}</strong>
                    <p>{item.rootCause}</p>
                  </div>
                  <div>
                    <span>{item.similarityScore.toFixed(2)}</span>
                    <small>{item.successfulFix}</small>
                  </div>
                </button>
              ))}
            </div>
          </article>
        </div>
      </section>
    );
  }

  function renderDashboard() {
    return (
      <>
        {renderSystemOverviewLayer()}
        {renderTelemetryLayer()}
        {dashboardIncident ? renderGraphLayer() : null}
        {dashboardIncident ? renderReasoningLayer() : null}
        {dashboardIncident ? renderRiskLayer() : null}
        {dashboardIncident ? renderFixLayer() : null}
        {dashboardIncident ? renderLearningLayer() : null}
      </>
    );
  }

  function renderLiveIncidents() {
    if (filteredLiveIncidents.length === 0) {
      return (
        <section className="mission-layer">
          <div className="mission-layer__header">
            <div>
              <p className="eyebrow">Live Incident Command</p>
              <h2>Active incidents</h2>
            </div>
            <span className="layer-tag">Real-time monitoring</span>
          </div>
          <article className="panel-card">
            <div className="panel-card__header">
              <div>
                <h3>No live incidents</h3>
                <p>BugOrbit will surface active incidents here as soon as telemetry analysis opens one.</p>
              </div>
            </div>
            <div className="detail-grid">
              <div className="detail-chip">
                <span>Active incidents</span>
                <strong>0</strong>
              </div>
              <div className="detail-chip">
                <span>Next step</span>
                <strong>Analyze telemetry or load demo mode</strong>
              </div>
            </div>
          </article>
        </section>
      );
    }

    return (
      <section className="mission-layer">
        <div className="mission-layer__header">
          <div>
            <p className="eyebrow">Live Incident Command</p>
            <h2>Active incidents</h2>
          </div>
          <span className="layer-tag">Real-time monitoring</span>
        </div>
        <div className="layer-grid layer-grid--2">
          <article className="panel-card">
            <div className="panel-card__header">
              <div>
                <h3>Incident List</h3>
                <p>Current high-severity incidents opened by BugOrbit.</p>
              </div>
            </div>
            <div className="incident-table">
              <div className="incident-table__head">
                <span>ID</span>
                <span>Primary Service</span>
                <span>Severity</span>
                <span>Status</span>
                <span>Affected</span>
                <span>Started</span>
              </div>
              {filteredLiveIncidents.map((incident) => (
                <button
                  type="button"
                  className={`incident-table__row ${displayedIncident?.id === incident.id ? "is-active" : ""}`}
                  key={incident.id}
                  onClick={() => {
                    setSelectedLiveIncidentId(incident.id);
                    setFixForm((current) => ({ ...current, incidentId: incident.id }));
                  }}
                >
                  <span>{incident.id}</span>
                  <span>{incident.primaryService}</span>
                  <span className={`severity-tag severity-tag--${incident.severity}`}>{incident.severity}</span>
                  <span>{incident.status}</span>
                  <span>{incident.affectedServicesCount}</span>
                  <span>{formatDate(incident.timeStarted)}</span>
                </button>
              ))}
            </div>
          </article>
          <article className="panel-card">
            <div className="panel-card__header">
              <div>
                <h3>Incident Summary</h3>
                <p>Focused command-center view for the currently active incident.</p>
              </div>
            </div>
            {displayedIncident ? (
              <div className="detail-grid">
                <div className="detail-chip">
                  <span>Primary Service</span>
                  <strong>{displayedIncident.primaryService}</strong>
                </div>
                <div className="detail-chip">
                  <span>Recent Deployment</span>
                  <strong>{displayedIncident.recentDeployment}</strong>
                </div>
                <div className="detail-chip">
                  <span>Suspected Error</span>
                  <strong>{displayedIncident.suspectedError}</strong>
                </div>
                <div className="detail-chip">
                  <span>Signals</span>
                  <strong>{displayedIncident.alertSignals.join(", ")}</strong>
                </div>
              </div>
            ) : null}
          </article>
        </div>
      </section>
    );
  }

  function renderResolvedIncidents() {
    const incident = filteredResolvedIncidents.find((entry) => entry.id === selectedResolvedId) ?? selectedResolvedIncident;
    return (
      <section className="mission-layer">
        <div className="mission-layer__header">
          <div>
            <p className="eyebrow">Incident Postmortem Explorer</p>
            <h2>Resolved incidents</h2>
          </div>
          <span className="layer-tag">Learning history</span>
        </div>
        <div className="layer-grid layer-grid--resolved">
          <article className="panel-card resolved-sidebar">
            <div className="panel-card__header">
              <div>
                <h3>Resolved Incident List</h3>
                <p>Search, filter, and compare historical incidents.</p>
              </div>
            </div>
            <div className="form-grid form-grid--compact">
              <label>
                Search by incident, service, error
                <input value={resolvedSearch} onChange={(event) => setResolvedSearch(event.target.value)} />
              </label>
              <label>
                Severity
                <select value={resolvedSeverityFilter} onChange={(event) => setResolvedSeverityFilter(event.target.value)}>
                  <option value="all">All</option>
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                </select>
              </label>
              <label>
                Resolution Type
                <select
                  value={resolvedResolutionTypeFilter}
                  onChange={(event) => setResolvedResolutionTypeFilter(event.target.value)}
                >
                  <option value="all">All</option>
                  {[...new Set(resolvedIncidents.map((entry) => entry.resolutionType).filter(Boolean))].map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Team
                <select value={resolvedTeamFilter} onChange={(event) => setResolvedTeamFilter(event.target.value)}>
                  <option value="all">All</option>
                  {[...new Set(resolvedIncidents.map((entry) => entry.ownerTeam))].map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Sort
                <select value={resolvedSort} onChange={(event) => setResolvedSort(event.target.value)}>
                  <option value="recent">Most recent</option>
                  <option value="longest">Longest resolution</option>
                  <option value="severity">Highest severity</option>
                </select>
              </label>
            </div>
            <div className="resolved-list">
              {filteredResolvedIncidents.map((entry) => (
                <button
                  type="button"
                  key={entry.id}
                  className={`resolved-card ${incident?.id === entry.id ? "is-selected" : ""}`}
                  onClick={() => setSelectedResolvedId(entry.id)}
                >
                  <div className="resolved-card__header">
                    <strong>{entry.id}</strong>
                    <span className={`severity-tag severity-tag--${entry.severity}`}>{entry.severity}</span>
                  </div>
                  <p>{entry.rootCause}</p>
                  <small>
                    {entry.primaryService} · Resolved · {formatDate(entry.resolvedAt ?? entry.timeStarted)} · {entry.resolutionDurationMinutes}m
                  </small>
                </button>
              ))}
            </div>
          </article>
          <article className="panel-card resolved-main">
            {incident ? (
              <>
                <div className="resolved-summary">
                  <div>
                    <p className="eyebrow">Incident Summary</p>
                    <h3>{incident.title}</h3>
                  </div>
                  <div className="chip-cluster">
                    <span className={`severity-tag severity-tag--${incident.severity}`}>{incident.severity}</span>
                    <span className="history-pill">Resolved</span>
                    <span className="history-pill">{incident.ownerTeam}</span>
                  </div>
                </div>
                <div className="overview-grid overview-grid--compact">
                  <article className="overview-card">
                    <span>Incident ID</span>
                    <strong>{incident.id}</strong>
                    <small>Primary service {incident.primaryService}</small>
                  </article>
                  <article className="overview-card">
                    <span>Created At</span>
                    <strong>{formatDate(incident.timeStarted)}</strong>
                    <small>Resolved {formatDate(incident.resolvedAt ?? incident.timeStarted)}</small>
                  </article>
                  <article className="overview-card">
                    <span>Resolution Duration</span>
                    <strong>{incident.resolutionDurationMinutes}m</strong>
                    <small>Owner team {incident.ownerTeam}</small>
                  </article>
                </div>

                <div className="resolved-sections">
                  <section className="resolved-section">
                    <h4>Root Cause Analysis</h4>
                    <div className="detail-grid">
                      <div className="detail-chip">
                        <span>Root Cause Service</span>
                        <strong>{incident.rootCauseService}</strong>
                      </div>
                      <div className="detail-chip">
                        <span>Error Type</span>
                        <strong>{incident.rootCauseErrorType}</strong>
                      </div>
                      <div className="detail-chip">
                        <span>Trigger Event</span>
                        <strong>{incident.triggerEvent}</strong>
                      </div>
                      <div className="detail-chip">
                        <span>Contributing Factors</span>
                        <strong>{incident.contributingFactors.join(", ")}</strong>
                      </div>
                    </div>
                    <div className="explanation-card">
                      <p>{incident.aiExplanation}</p>
                    </div>
                  </section>

                  <section className="resolved-section">
                    <h4>Service Impact</h4>
                    <div className="risk-table">
                      <div className="risk-table__head">
                        <span>Service</span>
                        <span>Risk</span>
                        <span>Impact Type</span>
                        <span>Status</span>
                      </div>
                      {incident.affectedServices.map((service) => (
                        <div className={`risk-table__row risk-table__row--${service.level}`} key={service.service}>
                          <span>{service.service}</span>
                          <span>{service.riskScore}%</span>
                          <span>{service.impactType}</span>
                          <span>{service.statusDuringIncident}</span>
                        </div>
                      ))}
                    </div>
                  </section>

                  <section className="resolved-section">
                    <h4>Propagation Path</h4>
                    <div className="propagation-list">
                      {incident.propagationPath.map((service, index) => (
                        <div className="propagation-step" key={service}>
                          <strong>{index + 1}</strong>
                          <span>{service}</span>
                        </div>
                      ))}
                    </div>
                  </section>

                  <section className="resolved-section">
                    <h4>Dependency Graph Snapshot</h4>
                    {renderGraphCanvas(buildResolvedGraphModel(incident))}
                  </section>

                  <section className="resolved-section">
                    <h4>Resolution Steps</h4>
                    <div className="resolution-grid">
                      {incident.resolutionSteps.map((step) => (
                        <article className="resolution-card" key={`${incident.id}-${step.step}`}>
                          <div className="resolution-card__header">
                            <strong>Step {step.step}</strong>
                            <span className={`resolution-badge resolution-badge--${step.result}`}>{step.result}</span>
                          </div>
                          <p>{step.action}</p>
                          <small>
                            {step.actor} · {formatDate(step.timestamp)}
                          </small>
                        </article>
                      ))}
                    </div>
                  </section>

                  <section className="resolved-section">
                    <h4>Final Resolution</h4>
                    <div className="final-resolution">
                      <p>
                        <strong>Final Resolution:</strong> {incident.finalResolution}
                      </p>
                      <p>
                        <strong>Resolved By:</strong> {incident.resolvedBy}
                      </p>
                      <p>
                        <strong>Resolution Type:</strong> {incident.resolutionType}
                      </p>
                      <p>
                        <strong>Post-fix Validation:</strong> {incident.postFixValidation}
                      </p>
                    </div>
                  </section>

                  <section className="resolved-section">
                    <h4>Timeline Replay</h4>
                    <div className="timeline-feed">
                      {incident.timelineReplay.map((event) => (
                        <div className="timeline-feed__item" key={`${event.timestamp}-${event.title}`}>
                          <div className="timeline-feed__dot" />
                          <div>
                            <strong>{event.title}</strong>
                            <p>{event.detail}</p>
                            <small>{formatDate(event.timestamp)}</small>
                          </div>
                        </div>
                      ))}
                    </div>
                  </section>

                  <section className="resolved-section">
                    <h4>Similar Incidents</h4>
                    <div className="similar-grid">
                      {incident.similarIncidents.map((item) => (
                        <button type="button" className="history-card" key={item.id} onClick={() => setSelectedResolvedId(item.id)}>
                          <div>
                            <strong>{item.id}</strong>
                            <p>{item.rootCause}</p>
                          </div>
                          <div>
                            <span>{item.similarityScore.toFixed(2)}</span>
                            <small>{item.successfulFix}</small>
                          </div>
                        </button>
                      ))}
                    </div>
                  </section>

                  <section className="resolved-section">
                    <h4>Lessons Learned / Notes</h4>
                    <div className="explanation-card">
                      <p>{incident.notes}</p>
                    </div>
                  </section>
                </div>
              </>
            ) : (
              <p className="muted">Select a resolved incident to inspect the postmortem explorer.</p>
            )}
          </article>
        </div>
      </section>
    );
  }

  function renderDependencyExplorer() {
    return (
      <section className="mission-layer">
        <div className="mission-layer__header">
          <div>
            <p className="eyebrow">Dependency Explorer</p>
            <h2>Search graph relationships</h2>
          </div>
          <span className="layer-tag">Blast radius focus</span>
        </div>
        <div className="layer-grid layer-grid--resolved">
          <article className="panel-card">
            <div className="form-grid">
              <label>
                Search Service
                <input value={selectedService} onChange={(event) => setSelectedService(event.target.value)} />
              </label>
              <label>
                Filter Edges
                <select value={edgeFilter} onChange={(event) => setEdgeFilter(event.target.value)}>
                  <option>All edges</option>
                  <option>DEPENDS_ON</option>
                  <option>IMPACTS</option>
                  <option>RESOLVED_BY</option>
                </select>
              </label>
            </div>
            <div className="detail-grid" style={{ marginTop: 20 }}>
              <div className="detail-chip">
                <span>Blast Radius</span>
                <strong>{displayedIncident?.affectedServicesCount ?? 0}</strong>
              </div>
              <div className="detail-chip">
                <span>Selected Node</span>
                <strong>{selectedService || "None"}</strong>
              </div>
            </div>
          </article>
          <article className="panel-card panel-card--wide">
            {renderGraphCanvas(buildGraphModel(displayedIncident))}
          </article>
        </div>
      </section>
    );
  }

  function renderFixMemory() {
    return (
      <section className="mission-layer">
        <div className="mission-layer__header">
          <div>
            <p className="eyebrow">Fix Memory</p>
            <h2>Resolution knowledge base</h2>
          </div>
          <span className="layer-tag">Success outcomes</span>
        </div>
        <article className="panel-card">
          <div className="memory-table">
            <div className="memory-table__head">
              <span>Error Type</span>
              <span>Service</span>
              <span>Fix Used</span>
              <span>Success Rate</span>
            </div>
            {fixMemorySeed.map((row) => (
              <div className="memory-table__row" key={`${row.errorType}-${row.service}`}>
                <span>{row.errorType}</span>
                <span>{row.service}</span>
                <span>{row.fix}</span>
                <span>
                  <div className="risk-meter">
                    <div style={{ width: `${row.successRate}%` }} />
                  </div>
                  {row.successRate}%
                </span>
              </div>
            ))}
          </div>
        </article>
      </section>
    );
  }

  function renderTelemetryExplorer() {
    return (
      <section className="mission-layer">
        <div className="mission-layer__header">
          <div>
            <p className="eyebrow">Telemetry Explorer</p>
            <h2>Signal inspection</h2>
          </div>
          <span className="layer-tag">Logs, alerts, metrics, traces</span>
        </div>
        {renderTelemetryLayer()}
      </section>
    );
  }

  function renderSimulationLab() {
    return (
      <section className="mission-layer">
        <div className="mission-layer__header">
          <div>
            <p className="eyebrow">Chaos Simulation Lab</p>
            <h2>Inject failure and predict outcomes</h2>
          </div>
          <span className="layer-tag">Cascade simulator</span>
        </div>
        <div className="layer-grid layer-grid--2">
          <article className="panel-card">
            <div className="form-grid">
              <label>
                Select Service
                <select value={simulationService} onChange={(event) => setSimulationService(event.target.value)}>
                  {simulationServiceOptions.map((service) => (
                    <option key={service} value={service}>
                      {service}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Inject Failure
                <select value={simulationFailure} onChange={(event) => setSimulationFailure(event.target.value)}>
                  {["DB Timeout", "Memory Leak", "Latency Spike"].map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                className="primary-button"
                onClick={() =>
                  setSimulationRun(buildSimulationScenario(simulationService, simulationFailure, result, submittedTrace))
                }
              >
                Run Simulation
              </button>
            </div>
          </article>
          <article className="panel-card simulation-card">
            <div className="panel-card__header">
              <div>
                <h3>Predicted Cascade</h3>
                <p>Watch propagation and likely remediations before changing production.</p>
              </div>
            </div>
            {simulationRun ? (
              <>
                <div className="simulation-summary">
                  <div className="detail-chip">
                    <span>Injected Service</span>
                    <strong>{simulationRun.service}</strong>
                  </div>
                  <div className="detail-chip">
                    <span>Failure Mode</span>
                    <strong>{simulationRun.failureType}</strong>
                  </div>
                  <div className="detail-chip">
                    <span>Blast Radius</span>
                    <strong>{simulationRun.predictedCascade.length} services</strong>
                  </div>
                </div>
                <div className="propagation-list">
                  {simulationRun.predictedCascade.map((service, index) => (
                    <div className="propagation-step" key={`${service}-${index}`}>
                      <strong>{index + 1}</strong>
                      <span>{service}</span>
                    </div>
                  ))}
                </div>
                <div className="simulation-recommendations">
                  <h4>Suggested recovery playbook</h4>
                <ul className="fix-recommendations">
                  {simulationRun.expectedFixes.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
                </div>
              </>
            ) : (
              <p className="muted">Run a chaos scenario to preview cascade depth and recovery options.</p>
            )}
          </article>
        </div>
      </section>
    );
  }

  function renderSettings() {
    return (
      <section className="mission-layer">
        <div className="mission-layer__header">
          <div>
            <p className="eyebrow">Settings</p>
            <h2>Platform controls</h2>
          </div>
          <span className="layer-tag">Environment</span>
        </div>
        <div className="overview-grid overview-grid--compact">
          <article className="overview-card">
            <span>Brand</span>
            <strong>BugOrbit</strong>
            <small>Graph-Powered Incident Intelligence</small>
          </article>
          <article className="overview-card">
            <span>API Endpoint</span>
            <strong>localhost:8010</strong>
            <small>BugOrbit backend</small>
          </article>
          <article className="overview-card">
            <span>Demo Mode</span>
            <strong>{demoMode ? "Enabled" : "Disabled"}</strong>
            <small>Mission replay ready</small>
          </article>
        </div>
      </section>
    );
  }

  function renderIntelligencePanelSection(
    key: keyof typeof collapsedSections,
    title: string,
    content: ReactNode
  ) {
    return (
      <section className="intelligence-section">
        <button type="button" className="intelligence-section__header" onClick={() => toggleSection(key)}>
          <strong>{title}</strong>
          <span>{collapsedSections[key] ? "+" : "-"}</span>
        </button>
        {!collapsedSections[key] ? <div className="intelligence-section__body">{content}</div> : null}
      </section>
    );
  }

  function renderIntelligencePanel() {
    return (
      <aside className="intelligence-panel">
        <div className="intelligence-panel__header">
          <p className="eyebrow">BugOrbit Intelligence Panel</p>
          <h2>Explainable incident control</h2>
        </div>
        {renderIntelligencePanelSection(
          "summary",
          "AI Summary",
          displayedIncident ? (
            <>
              <p>{displayedIncident.aiExplanation}</p>
              <div className="confidence-bar">
                <div style={{ width: `${Math.round(displayedIncident.confidence * 100)}%` }} />
              </div>
              <div className="detail-chip">
                <span>Confidence</span>
                <strong>{Math.round(displayedIncident.confidence * 100)}%</strong>
              </div>
            </>
          ) : (
            <p className="muted">Run analysis to populate the intelligence summary.</p>
          )
        )}
        {renderIntelligencePanelSection(
          "risk",
          "Risk Analysis",
          displayedIncident ? (
            <div className="mini-risk-list">
              {displayedIncident.affectedServices.map((service) => (
                <div className="mini-risk-row" key={service.service}>
                  <span>{service.service}</span>
                  <strong>{service.riskScore}%</strong>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted">No risk data yet.</p>
          )
        )}
        {renderIntelligencePanelSection(
          "fixes",
          "Recommended Fixes",
          <ul className="fix-recommendations">
            {(displayedIncident?.recommendations ?? ["No recommendations available yet."]).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        )}
        {renderIntelligencePanelSection(
          "entry",
          "Fix Entry",
          <div className="form-grid form-grid--compact">
            {fixSubmitSuccess ? <div className="success-banner">{fixSubmitSuccess}</div> : null}
            {fixSubmitError ? <div className="error-banner">{fixSubmitError}</div> : null}
            <label>
              Live Incident
              <select
                value={fixForm.incidentId}
                onChange={(event) => setFixForm((current) => ({ ...current, incidentId: event.target.value }))}
              >
                {liveIncidentOptions.length === 0 ? (
                  <option value="">No live incidents available</option>
                ) : (
                  liveIncidentOptions.map((incident) => (
                    <option key={incident.id} value={incident.id}>
                      {incident.id} · {incident.primaryService} · {incident.severity}
                    </option>
                  ))
                )}
              </select>
            </label>
            <label>
              Action Taken
              <input
                value={fixForm.actionTaken}
                onChange={(event) => setFixForm((current) => ({ ...current, actionTaken: event.target.value }))}
              />
            </label>
            <label>
              Result
              <select
                value={fixForm.result}
                onChange={(event) => setFixForm((current) => ({ ...current, result: event.target.value as FixEntry["result"] }))}
              >
                <option value="Success">Success</option>
                <option value="Failed">Failed</option>
              </select>
            </label>
            <label>
              Feedback
              <select
                value={fixForm.feedback}
                onChange={(event) => setFixForm((current) => ({ ...current, feedback: event.target.value as FixEntry["feedback"] }))}
              >
                <option value="Improved">Improved</option>
                <option value="Resolved">Resolved</option>
                <option value="Needs follow-up">Needs follow-up</option>
              </select>
            </label>
            <label>
              Notes
              <textarea
                value={fixForm.notes}
                onChange={(event) => setFixForm((current) => ({ ...current, notes: event.target.value }))}
              />
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={fixForm.finalResolution}
                onChange={(event) => setFixForm((current) => ({ ...current, finalResolution: event.target.checked }))}
              />
              Final Resolution Toggle
            </label>
            <button
              type="button"
              className="primary-button"
              onClick={submitFixEntry}
              disabled={liveIncidentOptions.length === 0 || fixSubmitting}
            >
              {fixSubmitting ? "Recording..." : "Record Fix"}
            </button>
          </div>
        )}
        {renderIntelligencePanelSection(
          "memory",
          "Learning Loop",
          <div className="memory-timeline">
            {(scopedFixEntries.length > 0 ? scopedFixEntries : []).map((entry) => (
              <article className="memory-card" key={entry.id}>
                <strong>{entry.actionTaken}</strong>
                <p>{entry.incidentId}</p>
                <p>{entry.notes || "No notes provided."}</p>
                <small>{entry.finalResolution ? "Final resolution" : `${entry.result} · ${entry.feedback}`}</small>
              </article>
            ))}
            {scopedFixEntries.length === 0 ? <p className="muted">Fix actions recorded here will feed BugOrbit memory.</p> : null}
          </div>
        )}
      </aside>
    );
  }

  function renderWorkspace() {
    if (activeView === "dashboard") return renderDashboard();
    if (activeView === "incidents") return renderLiveIncidents();
    if (activeView === "resolved") return renderResolvedIncidents();
    if (activeView === "graph") return renderDependencyExplorer();
    if (activeView === "memory") return renderFixMemory();
    if (activeView === "telemetry") return renderTelemetryExplorer();
    if (activeView === "simulation") return renderSimulationLab();
    return renderSettings();
  }

  return (
    <div className="bugorbit-shell">
      <header className="mission-topbar">
        <div className="brand-cluster">
          <div className="brand-mark">
            <span className="brand-orbit brand-orbit--one" />
            <span className="brand-orbit brand-orbit--two" />
            <strong>BO</strong>
          </div>
          <div>
            <strong>BugOrbit</strong>
            <span>Graph-Powered Incident Intelligence</span>
          </div>
        </div>
        <div className={`status-indicator status-indicator--${systemStatus}`}>
          <span className="status-dot" />
          {systemStatus === "critical" ? "Critical" : systemStatus === "warning" ? "Warning" : "Healthy"}
        </div>
        <div className="topbar-search">
          <input
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="Search service, incident ID, error type"
          />
          {searchTerm.trim().length > 0 && (
            <div className="topbar-search-results">
              {allIncidents
                .filter((incident) => {
                  const q = searchTerm.trim().toLowerCase();
                  return [incident.id, incident.primaryService, incident.suspectedError ?? (incident as any).rootCauseErrorType]
                    .some((v) => v?.toLowerCase().includes(q));
                })
                .map((incident) => (
                  <div
                    key={incident.id}
                    className="search-result-item"
                    onClick={() => {
                      setSearchTerm("");
                      if (incident.status === "active") {
                        setActiveView("incidents");
                      } else {
                        setActiveView("resolved");
                        setSelectedResolvedId(incident.id);
                      }
                    }}
                  >
                    <strong>{incident.id}</strong> — {incident.primaryService} ({incident.status})
                  </div>
                ))}
              {allIncidents.filter((incident) => {
                const q = searchTerm.trim().toLowerCase();
                return [incident.id, incident.primaryService, incident.suspectedError ?? (incident as any).rootCauseErrorType]
                  .some((v) => v?.toLowerCase().includes(q));
              }).length === 0 && (
                <div className="search-result-item" style={{ color: "var(--muted)", cursor: "default" }}>
                  No results found
                </div>
              )}
            </div>
          )}
        </div>
        <div className="topbar-actions">
          <div className="history-pill">Active {activeIncidents.length}</div>
          <button type="button" className="ghost-button" onClick={handleDemoMode}>
            Demo Mode
          </button>
          <div className="profile-avatar">NJ</div>
        </div>
      </header>

      <div className={`mission-layout ${activeView !== "incidents" ? "mission-layout--no-panel" : ""}`}>
        <aside className="mission-sidebar">
          <div className="mission-sidebar__nav">
            {navItems.map((item) => (
              <button
                type="button"
                key={item.id}
                className={`mission-sidebar__link ${activeView === item.id ? "is-active" : ""}`}
                onClick={() => setActiveView(item.id)}
              >
                <span className="mission-sidebar__icon">{item.icon}</span>
                <span>{item.label}</span>
              </button>
            ))}
          </div>
          <div className="mission-sidebar__footer">
            <p className="eyebrow">Visible lifecycle</p>
            <p>{"Telemetry -> Signals -> Graph -> AI -> Risk -> Fix -> Memory"}</p>
          </div>
        </aside>

        <main className="mission-workspace">
          <section className="hero-panel">
            <div>
              <p className="eyebrow">BugOrbit Mission Control</p>
              <h1>{activeView === "dashboard" ? "Pipeline-driven incident intelligence" : navItems.find((item) => item.id === activeView)?.label}</h1>
              <p>
                Watch telemetry enter the system, see the graph evolve, inspect AI reasoning, trace propagation,
                execute fixes, and store learning memory in one connected workspace.
              </p>
            </div>
            <div className="hero-panel__actions">
              {/* Buttons consolidated to Telemetry block */}
            </div>
          </section>

          {renderPipeline()}
          {error ? <div className="error-banner">{error}</div> : null}
          {incidentStateError ? <div className="error-banner">{incidentStateError}</div> : null}
          {renderWorkspace()}
        </main>

        {activeView === "incidents" ? renderIntelligencePanel() : null}
      </div>
    </div>
  );
}

export default App;
