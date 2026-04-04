from __future__ import annotations

import json
from pathlib import Path

from app.models.schemas import IncidentRecord


class IncidentVectorStore:
    def __init__(self, data_path: str | Path) -> None:
        self.data_path = Path(data_path)
        self._incidents = self._load_incidents()

    def _load_incidents(self) -> list[IncidentRecord]:
        if not self.data_path.exists():
            return []
        payload = json.loads(self.data_path.read_text())
        return [IncidentRecord(**item) for item in payload]

    def search(self, query: str, top_k: int = 3) -> list[IncidentRecord]:
        terms = {token.lower() for token in query.split() if token.strip()}
        scored: list[tuple[int, IncidentRecord]] = []
        for incident in self._incidents:
            haystack = " ".join(
                [
                    incident.title,
                    incident.summary,
                    incident.root_cause,
                    " ".join(incident.services),
                    " ".join(incident.symptoms),
                ]
            ).lower()
            score = sum(term in haystack for term in terms)
            if score:
                scored.append((score, incident))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [incident for _, incident in scored[:top_k]]
