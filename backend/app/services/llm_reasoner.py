from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.config import settings
from app.models.schemas import GraphQueryResult, IncidentRecord, ImpactAnalysis, StructuredTrace, TraceAnalysis


class OpenAIReasoningService:
    def is_enabled(self) -> bool:
        return settings.llm_provider.lower() == "openai" and bool(settings.openai_api_key)

    def synthesize_incident_response(
        self,
        structured_trace: StructuredTrace,
        trace_analysis: TraceAnalysis,
        graph_result: GraphQueryResult,
        impact_analysis: ImpactAnalysis,
        incident_matches: list[IncidentRecord],
    ) -> tuple[str, list[str], float] | None:
        if not self.is_enabled():
            return None

        payload = {
            "model": settings.openai_model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You are an SRE incident analyst for RocketRide. "
                                "Use only the supplied telemetry, graph impact data, and incident history. "
                                "Return concise JSON with a probable root cause, actionable solutions, and a confidence score."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": self._build_evidence_prompt(
                                structured_trace,
                                trace_analysis,
                                graph_result,
                                impact_analysis,
                                incident_matches,
                            ),
                        }
                    ],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "incident_reasoning",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "root_cause": {"type": "string"},
                            "solutions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "minItems": 1,
                                "maxItems": 5,
                            },
                            "confidence_score": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                            },
                        },
                        "required": ["root_cause", "solutions", "confidence_score"],
                        "additionalProperties": False,
                    },
                }
            },
        }

        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=settings.openai_timeout_seconds) as client:
                response = client.post(
                    f"{settings.openai_base_url.rstrip('/')}/responses",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPError:
            return None

        content_text = self._extract_text(response.json())
        if not content_text:
            return None

        try:
            parsed = json.loads(content_text)
        except json.JSONDecodeError:
            return None

        root_cause = str(parsed.get("root_cause", "")).strip()
        solutions = [str(item).strip() for item in parsed.get("solutions", []) if str(item).strip()]
        confidence = float(parsed.get("confidence_score", 0.0))

        if not root_cause or not solutions:
            return None

        return root_cause, solutions, max(0.0, min(1.0, confidence))

    def _build_evidence_prompt(
        self,
        structured_trace: StructuredTrace,
        trace_analysis: TraceAnalysis,
        graph_result: GraphQueryResult,
        impact_analysis: ImpactAnalysis,
        incident_matches: list[IncidentRecord],
    ) -> str:
        evidence = {
            "structured_trace": {
                "trace_id": structured_trace.trace_id,
                "provider": structured_trace.provider,
                "root_service": structured_trace.root_service,
                "root_endpoint": structured_trace.root_endpoint,
                "error_type": structured_trace.error_type,
                "latency_ms": structured_trace.latency_ms,
                "telemetry_summary": structured_trace.telemetry_summary,
            },
            "trace_analysis": trace_analysis.model_dump(),
            "graph_result": graph_result.model_dump(),
            "impact_analysis": impact_analysis.model_dump(),
            "incident_matches": [incident.model_dump() for incident in incident_matches],
        }
        return (
            "Analyze this incident and infer the most likely root cause. "
            "Prefer causes supported by correlated telemetry and similar incidents. "
            "Return 2-4 actionable remediations.\n\n"
            f"{json.dumps(evidence, indent=2)}"
        )

    def _extract_text(self, body: dict[str, Any]) -> str | None:
        output = body.get("output", [])
        for item in output:
            for content in item.get("content", []):
                text = content.get("text")
                if text:
                    return str(text)
        return None
