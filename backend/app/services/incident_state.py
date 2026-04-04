from __future__ import annotations

import json
from collections import OrderedDict
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock

from app.db.neo4j import Neo4jService
from app.models.schemas import (
    AnalysisNarrative,
    FinalAnalysisResponse,
    GraphQueryResult,
    ImpactAnalysis,
    IncidentFixRequest,
    IncidentRecord,
    IncidentStateResponse,
    RuntimeAffectedService,
    RuntimeIncidentRecord,
    RuntimeResolutionStep,
    RuntimeSimilarIncident,
    RuntimeTimelineEvent,
    StructuredTrace,
    TraceAnalysis,
    TraceIngestRequest,
)


class IncidentStateService:
    def __init__(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        self._state_path = repo_root / "data" / "incidents" / "runtime_state.json"
        self._lock = RLock()
        self._neo4j = Neo4jService()
        self._active: OrderedDict[str, RuntimeIncidentRecord] = OrderedDict()
        self._resolved: OrderedDict[str, RuntimeIncidentRecord] = OrderedDict()
        self._load()

    def upsert_analysis(
        self,
        request: TraceIngestRequest,
        response: FinalAnalysisResponse,
    ) -> RuntimeIncidentRecord:
        incident = self._build_incident_from_analysis(request, response)
        with self._lock:
            existing = self._active.get(incident.id) or self._resolved.get(incident.id)
            if existing:
                incident.resolution_steps = existing.resolution_steps
            target = self._resolved if incident.status == "resolved" else self._active
            other = self._active if target is self._resolved else self._resolved
            other.pop(incident.id, None)
            target[incident.id] = incident
            self._neo4j.sync_runtime_incident(incident)
            self._persist()
        return incident

    def record_fix(self, request: IncidentFixRequest) -> IncidentStateResponse:
        with self._lock:
            incident = self._active.get(request.incident_id) or self._resolved.get(request.incident_id)
            if incident is None:
                raise KeyError(request.incident_id)

            resolution_step = RuntimeResolutionStep(
                step=len(incident.resolution_steps) + 1,
                action=request.action_taken,
                actor=request.actor,
                timestamp=self._now_iso(),
                result="success" if request.final_resolution or request.result == "Success" else "failed",
                feedback=request.feedback,
                notes=request.notes,
            )
            incident.resolution_steps.append(resolution_step)
            incident.notes = request.notes or incident.notes
            self._neo4j.sync_incident_fix(incident.id, incident.id, incident.propagation_path, resolution_step)

            if request.final_resolution:
                incident.status = "resolved"
                incident.resolved_at = resolution_step.timestamp
                incident.resolution_duration_minutes = self._duration_minutes(incident.time_started, incident.resolved_at)
                incident.final_resolution = request.action_taken
                incident.resolved_by = request.actor
                incident.resolution_type = "Manual recovery"
                incident.post_fix_validation = self._post_fix_validation(request.feedback)
                incident.timeline_replay.append(
                    RuntimeTimelineEvent(
                        timestamp=resolution_step.timestamp,
                        title="Incident resolved",
                        detail=request.notes or request.action_taken,
                    )
                )
                self._active.pop(incident.id, None)
                self._resolved[incident.id] = incident
                self._neo4j.sync_incident_resolution(incident.id, incident.id, incident.propagation_path, incident)
            else:
                self._active[incident.id] = incident

            self._persist()
            return self.state()

    def state(self) -> IncidentStateResponse:
        with self._lock:
            return IncidentStateResponse(
                active=list(self._active.values()),
                resolved=list(reversed(list(self._resolved.values()))),
            )

    def _build_incident_from_analysis(
        self,
        request: TraceIngestRequest,
        response: FinalAnalysisResponse,
    ) -> RuntimeIncidentRecord:
        structured_trace = response.structured_trace
        trace_analysis = response.trace_analysis
        graph_result = response.graph_result
        impact_analysis = response.impact_analysis
        narrative = response.narrative
        incident_matches = response.incident_matches
        propagation_path = self._propagation_path(trace_analysis.failure_point, graph_result, impact_analysis)
        time_started = request.alerts[0].triggered_at if request.alerts else self._now_iso()

        return RuntimeIncidentRecord(
            id=structured_trace.trace_id,
            title="Live incident analysis",
            primary_service=trace_analysis.failure_point,
            severity=impact_analysis.severity,
            status="active",
            affected_services_count=len(propagation_path),
            time_started=time_started,
            owner_team=self._owner_team(request),
            suspected_error=structured_trace.error_type or "UnknownError",
            recent_deployment=self._recent_deployment(request),
            alert_signals=[alert.name for alert in request.alerts[:3]],
            propagation_path=propagation_path,
            root_cause=response.root_cause,
            root_cause_service=propagation_path[0] if propagation_path else trace_analysis.failure_point,
            root_cause_error_type=structured_trace.error_type or "UnknownError",
            trigger_event=self._trigger_event(request),
            contributing_factors=request.incident_hints,
            ai_explanation=narrative.executive_summary,
            affected_services=self._affected_services(propagation_path, time_started),
            timeline_replay=[
                RuntimeTimelineEvent(
                    timestamp=time_started,
                    title="Telemetry ingested",
                    detail="RocketRide opened a live incident from correlated telemetry.",
                ),
                RuntimeTimelineEvent(
                    timestamp=self._now_iso(),
                    title="AI reasoning completed",
                    detail=narrative.executive_summary,
                ),
            ],
            notes=". ".join(request.incident_hints) if request.incident_hints else None,
            confidence=response.confidence_score,
            recommendations=narrative.recommended_actions or response.solutions,
            similar_incidents=self._similar_incidents(incident_matches),
        )

    def _affected_services(self, propagation_path: list[str], timestamp: str) -> list[RuntimeAffectedService]:
        services: list[RuntimeAffectedService] = []
        for index, service in enumerate(propagation_path):
            risk_score = max(50, 96 - index * 10)
            services.append(
                RuntimeAffectedService(
                    service=service,
                    risk_score=risk_score,
                    level="critical" if risk_score >= 90 else "high" if risk_score >= 75 else "medium",
                    dependency_distance=index,
                    impact_type="root-cause" if index == 0 else "direct" if index == 1 else "downstream",
                    status_during_incident="failing" if risk_score >= 80 else "degraded",
                    risk_explanation=f"{service} is in the active propagation path with computed risk {risk_score}%.",
                    last_incident_at=timestamp,
                )
            )
        return services

    def _similar_incidents(self, incident_matches: list[IncidentRecord]) -> list[RuntimeSimilarIncident]:
        items: list[RuntimeSimilarIncident] = []
        for index, incident in enumerate(incident_matches):
            items.append(
                RuntimeSimilarIncident(
                    id=incident.incident_id,
                    resolution=incident.fix[0] if incident.fix else incident.root_cause,
                    similarity_score=max(0.55, 0.9 - index * 0.08),
                    root_cause=incident.root_cause,
                    successful_fix=incident.fix[0] if incident.fix else "Unknown",
                )
            )
        return items

    def _propagation_path(
        self,
        failure_point: str,
        graph_result: GraphQueryResult,
        impact_analysis: ImpactAnalysis,
    ) -> list[str]:
        return list(
            OrderedDict.fromkeys(
                [failure_point, *graph_result.affected_services, *impact_analysis.blast_radius]
            ).keys()
        )

    def _owner_team(self, request: TraceIngestRequest) -> str:
        for log in request.logs:
            for tag in log.tags:
                if tag.key.lower() == "team":
                    return tag.value
        return "operations"

    def _recent_deployment(self, request: TraceIngestRequest) -> str:
        if not request.deployments:
            return "No deployment signal available"
        deployment = request.deployments[0]
        return f"{deployment.service} {deployment.version}"

    def _trigger_event(self, request: TraceIngestRequest) -> str:
        if request.deployments:
            deployment = request.deployments[0]
            return f"{deployment.service} {deployment.version} deployment"
        return "Telemetry anomaly burst"

    def _post_fix_validation(self, feedback: str) -> str:
        if feedback == "Resolved":
            return "Service health normalized and follow-up validation passed."
        if feedback == "Improved":
            return "Primary symptoms improved and continued monitoring is recommended."
        return "Further remediation is still required."

    def _duration_minutes(self, started_at: str, ended_at: str | None) -> int | None:
        if ended_at is None:
            return None
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
        return max(1, int((end - start).total_seconds() // 60))

    def _load(self) -> None:
        if not self._state_path.exists():
            return
        payload = json.loads(self._state_path.read_text())
        self._active = OrderedDict(
            (item["id"], RuntimeIncidentRecord.model_validate(item)) for item in payload.get("active", [])
        )
        self._resolved = OrderedDict(
            (item["id"], RuntimeIncidentRecord.model_validate(item)) for item in payload.get("resolved", [])
        )

    def _persist(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(
            json.dumps(
                {
                    "active": [item.model_dump() for item in self._active.values()],
                    "resolved": [item.model_dump() for item in self._resolved.values()],
                },
                indent=2,
            )
        )

    def _now_iso(self) -> str:
        return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


incident_state_service = IncidentStateService()
