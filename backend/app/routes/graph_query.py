from fastapi import APIRouter

from app.db.neo4j import Neo4jService
from app.models.schemas import GraphQueryRequest, GraphQueryResult
from app.services.graph_query import GraphQueryService


router = APIRouter()
query_service = GraphQueryService()
neo4j_service = Neo4jService()


@router.post("", response_model=GraphQueryResult)
async def graph_query(request: GraphQueryRequest) -> GraphQueryResult:
    cypher = query_service.generate_cypher(request.service_name)
    return neo4j_service.query_impacted_services(request.service_name, cypher)
