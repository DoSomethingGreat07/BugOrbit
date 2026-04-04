from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import analyze, graph_query, incident_search, telemetry, trace


app = FastAPI(
    title="RocketRide AI",
    version="0.1.0",
    description="Agentic incident analysis API for telemetry, graph impact analysis, and incident retrieval.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trace.router, prefix="/trace", tags=["trace"])
app.include_router(analyze.router, prefix="/analyze", tags=["analyze"])
app.include_router(telemetry.router, prefix="/telemetry", tags=["telemetry"])
app.include_router(graph_query.router, prefix="/graph-query", tags=["graph"])
app.include_router(incident_search.router, prefix="/incident", tags=["incident"])


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
