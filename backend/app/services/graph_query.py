from __future__ import annotations

from app.models.schemas import GraphQueryResult


class GraphQueryService:
    def generate_cypher(self, service_name: str) -> str:
        return (
            f'MATCH (s:Service {{name: "{service_name}"}})-[:DEPENDS_ON|CALLS*1..3]->(dep:Service) '
            "RETURN DISTINCT dep.name AS service"
        )

    def build_result(self, service_name: str, affected_services: list[str]) -> GraphQueryResult:
        cypher = self.generate_cypher(service_name)
        relationships = [{"source": service_name, "target": target} for target in affected_services]
        return GraphQueryResult(cypher=cypher, affected_services=affected_services, relationships=relationships)
