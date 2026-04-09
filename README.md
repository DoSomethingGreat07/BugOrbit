# BugOrbit

BugOrbit is a graph-powered incident intelligence platform for turning raw production telemetry into structured incidents, dependency-aware impact analysis, remediation guidance, and live incident lifecycle state. It is designed to help engineering teams move from detection to investigation to resolution with more context and less guesswork.

This repository includes:

- a FastAPI backend for telemetry normalization, trace analysis, graph persistence, incident state, and recommendation generation
- a React + Vite frontend for live incident monitoring, graph exploration, fix recording, and simulation
- a Streamlit demo console for presenting backend results in a compact walkthrough UI
- sample telemetry payloads and incident data for local testing
- prompt files that support the reasoning workflows used in the system

## What The Platform Does

BugOrbit is built around a single operational workflow:

1. ingest raw telemetry or live telemetry-style payloads
2. normalize data into a consistent internal schema
3. reconstruct a structured trace and infer the likely failure point
4. query service relationships from Neo4j or a fallback dependency map
5. estimate blast radius and critical propagation paths
6. retrieve similar incidents and synthesize remediation guidance
7. create or update runtime incident state for active and resolved incidents
8. allow operators to record fixes and close incidents from the UI

The result is a dashboard driven by runtime analysis state rather than hardcoded summary cards or static demo data.

## Core Capabilities

- Telemetry normalization from loose payloads into strict backend schema models
- Structured trace ingestion for spans, logs, metrics, alerts, errors, deployments, host signals, and dependencies
- Failure point detection and suspected issue summarization
- Graph-backed service impact exploration with Neo4j
- Blast radius analysis and critical path estimation
- Similar incident retrieval from a local incident corpus
- AI-assisted root-cause narratives and recommended actions
- Runtime incident lifecycle tracking for active and resolved incidents
- Fix recording with resolution history synced back into incident state and graph state

## Architecture Overview

```text
Raw Telemetry / Live Telemetry
  -> Telemetry Normalization
  -> Structured Trace
  -> Trace Analysis
  -> Graph Sync + Graph Query
  -> Impact Analysis
  -> Similar Incident Retrieval
  -> Narrative + Recommendations
  -> Runtime Incident State
  -> Frontend / Demo Console
```

### Backend flow

The main orchestration pipeline lives in [backend/app/services/orchestrator.py](/Users/nikhiljuluri/Desktop/BugOrbit1/backend/app/services/orchestrator.py). A typical analysis request follows this sequence:

1. normalize the incoming payload
2. build a `StructuredTrace`
3. identify the likely failure point
4. sync trace context into Neo4j
5. query impacted services from the graph
6. estimate blast radius and severity
7. search similar historical incidents
8. synthesize root cause, recommendations, and a narrative
9. write the resulting incident into runtime state

### Main components

- [backend/app/routes/trace.py](/Users/nikhiljuluri/Desktop/BugOrbit1/backend/app/routes/trace.py): normalize and parse a raw telemetry payload into a structured trace
- [backend/app/routes/analyze.py](/Users/nikhiljuluri/Desktop/BugOrbit1/backend/app/routes/analyze.py): run the full BugOrbit analysis pipeline
- [backend/app/routes/telemetry.py](/Users/nikhiljuluri/Desktop/BugOrbit1/backend/app/routes/telemetry.py): accept OpenTelemetry-style or live telemetry payloads
- [backend/app/routes/graph_query.py](/Users/nikhiljuluri/Desktop/BugOrbit1/backend/app/routes/graph_query.py): query impacted services for a target service
- [backend/app/routes/incident_search.py](/Users/nikhiljuluri/Desktop/BugOrbit1/backend/app/routes/incident_search.py): incident search, runtime state snapshots, and fix recording
- [backend/app/services/incident_state.py](/Users/nikhiljuluri/Desktop/BugOrbit1/backend/app/services/incident_state.py): file-backed runtime incident state and lifecycle management
- [frontend/src/App.tsx](/Users/nikhiljuluri/Desktop/BugOrbit1/frontend/src/App.tsx): main dashboard application
- [frontend/src/services/api.ts](/Users/nikhiljuluri/Desktop/BugOrbit1/frontend/src/services/api.ts): frontend API integration layer
- [streamlit_app.py](/Users/nikhiljuluri/Desktop/BugOrbit1/streamlit_app.py): presentation-oriented incident console

## Repository Structure

```text
BugOrbit/
├── agents/                  # Prompt files and agent support assets
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── core/            # Configuration
│   │   ├── db/              # Neo4j and vector-db adapters
│   │   ├── models/          # Pydantic schema definitions
│   │   ├── routes/          # HTTP endpoints
│   │   └── services/        # Normalization, analysis, graph, state, RAG
│   ├── .env.example         # Backend environment template
│   └── requirements.txt     # Python dependencies
├── data/
│   └── incidents/           # Sample incidents and runtime state
├── frontend/                # React + Vite dashboard
├── docker-compose.yml       # Local backend/frontend/neo4j stack
├── live_telemetry_sample.json
├── sample.json
└── streamlit_app.py
```

## Product Surfaces

### React dashboard

The frontend exposes multiple views backed by live API data:

- Dashboard
- Live Incidents
- Resolved Incidents
- Dependency Explorer
- Fix Memory
- Telemetry Explorer
- Simulation Lab
- Settings

The dashboard fetches runtime incident state from the backend and updates when new incidents are analyzed or when a fix is recorded.

### Streamlit demo console

The repo also contains a Streamlit app in [streamlit_app.py](/Users/nikhiljuluri/Desktop/BugOrbit1/streamlit_app.py). It is useful for demos, quick reviews of analysis output, and visualizing graph neighborhoods without opening the React dashboard.

## Data Model Highlights

The canonical request and response models live in [backend/app/models/schemas.py](/Users/nikhiljuluri/Desktop/BugOrbit1/backend/app/models/schemas.py).

Important request-side models include:

- `TraceIngestRequest`
- `LiveTelemetryRequest`
- `Span`
- `LogRecord`
- `MetricRecord`
- `AlertRecord`
- `ErrorRecord`
- `DeploymentRecord`
- `HostSignalRecord`
- `ServiceDependency`

Important response-side models include:

- `StructuredTrace`
- `TraceAnalysis`
- `GraphQueryResult`
- `ImpactAnalysis`
- `FinalAnalysisResponse`
- `IncidentStateResponse`
- `RuntimeIncidentRecord`

## Runtime Incident Lifecycle

BugOrbit keeps an application-level incident state that is persisted to a local JSON file and mirrored into Neo4j when available.

Runtime state file:

- [data/incidents/runtime_state.json](/Users/nikhiljuluri/Desktop/BugOrbit1/data/incidents/runtime_state.json)

Lifecycle behavior:

1. a telemetry analysis creates or refreshes an active incident
2. incident details are enriched with impact, recommendations, and similar incidents
3. the frontend reads active and resolved incidents from `/incident/state`
4. recording a fix appends a resolution step to the incident timeline
5. marking a final resolution moves the incident from active to resolved

The runtime incident model includes fields for:

- severity
- owner team
- propagation path
- recommendations
- confidence score
- similar incidents
- timeline replay
- resolution steps

## Graph Layer

When Neo4j is enabled, the backend persists graph entities such as:

- `Tenant`
- `Trace`
- `Service`
- `Span`
- `Log`
- `Metric`
- `Alert`
- `Deployment`
- `Host`
- `Incident`
- `Hypothesis`
- `FixAction`

Representative relationship types include:

- `CALLS`
- `DEPENDS_ON`
- `PARENT_OF`
- `IMPACTS`
- `ROOT_CAUSE`
- `HAS_FIX_ACTION`
- `SIMILAR_TO`

If Neo4j is unavailable, the backend can continue operating with reduced graph depth by relying on internal fallback behavior instead of failing the full pipeline.

## API Summary

The FastAPI application is defined in [backend/app/main.py](/Users/nikhiljuluri/Desktop/BugOrbit1/backend/app/main.py).

Base route groups:

- `/health`
- `/trace`
- `/analyze`
- `/telemetry`
- `/graph-query`
- `/incident`

### Main endpoints

`GET /health`

- basic health check

`POST /trace`

- accepts a raw telemetry payload
- normalizes it if needed
- returns a `StructuredTrace`

`POST /analyze`

- runs the full BugOrbit analysis pipeline
- returns a `FinalAnalysisResponse`

`POST /telemetry/normalize`

- accepts live telemetry input
- adapts it into the internal schema
- returns a normalized `StructuredTrace`

`POST /telemetry/analyze`

- runs full analysis on live telemetry input

`POST /graph-query`

- accepts a service name
- returns affected services and graph relationships

`POST /incident/search`

- searches the local incident corpus using a text query

`GET /incident/state`

- returns active incidents and resolved incidents

`POST /incident/fix`

- records a fix against an incident
- optionally marks the incident as resolved

## Sample Payloads

Two sample files are included for local testing:

- [sample.json](/Users/nikhiljuluri/Desktop/BugOrbit1/sample.json)
- [live_telemetry_sample.json](/Users/nikhiljuluri/Desktop/BugOrbit1/live_telemetry_sample.json)

Typical scenarios:

- use `sample.json` with `/trace` or `/analyze`
- use `live_telemetry_sample.json` with `/telemetry/normalize` or `/telemetry/analyze`

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 20+
- npm
- Docker Desktop or a local Neo4j 5.x instance if you want the full graph-backed stack

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd BugOrbit1
```

### 2. Configure backend environment

Copy the backend template:

```bash
cp backend/.env.example backend/.env
```

Available backend settings from [backend/.env.example](/Users/nikhiljuluri/Desktop/BugOrbit1/backend/.env.example):

```bash
APP_NAME=RocketRide AI
NEO4J_ENABLED=true
NEO4J_URI=bolt://neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
NEO4J_DATABASE=neo4j
NEO4J_BOOTSTRAP_DEMO_DATA=true
VECTOR_TOP_K=3
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-4.1-mini
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_TIMEOUT_SECONDS=20
```

Notes:

- for local non-Docker runs, `NEO4J_URI` is commonly `bolt://localhost:7687`
- `OPENAI_API_KEY` is required if you want live OpenAI-backed reasoning
- if you only want to explore parts of the pipeline locally, you can disable Neo4j by setting `NEO4J_ENABLED=false`

### 3. Configure frontend environment

This repo currently does not include a checked-in `frontend/.env.example`, so create the file manually:

```bash
printf 'VITE_API_BASE_URL=http://localhost:8000\n' > frontend/.env
```

The frontend API client defaults to `http://localhost:8010` when no variable is set, so creating `frontend/.env` is strongly recommended for local development.

## Run Locally

### Option 1: Manual development mode

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Optional Streamlit demo console:

```bash
streamlit run streamlit_app.py
```

Default local URLs:

- frontend: `http://localhost:5173`
- backend: `http://localhost:8000`
- streamlit: `http://localhost:8501`

### Option 2: Docker Compose

```bash
docker compose up --build
```

This starts:

- backend on `http://localhost:8000`
- frontend on `http://localhost:5173`
- Neo4j Browser on `http://localhost:7474`
- Neo4j Bolt on `bolt://localhost:7687`

The compose file uses [docker-compose.yml](/Users/nikhiljuluri/Desktop/BugOrbit1/docker-compose.yml) and loads backend configuration from `backend/.env.example` by default, so update that workflow if you want custom local secrets or a real API key in containers.

## Example Usage

### Health check

```bash
curl http://localhost:8000/health
```

### Normalize and parse a raw payload

```bash
curl -X POST http://localhost:8000/trace \
  -H "Content-Type: application/json" \
  -d @sample.json
```

### Run full analysis

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d @sample.json
```

### Analyze live telemetry

```bash
curl -X POST http://localhost:8000/telemetry/analyze \
  -H "Content-Type: application/json" \
  -d @live_telemetry_sample.json
```

### Query graph neighborhood for a service

```bash
curl -X POST http://localhost:8000/graph-query \
  -H "Content-Type: application/json" \
  -d '{"service_name":"payment-service"}'
```

### Read incident state

```bash
curl http://localhost:8000/incident/state
```

### Record a fix

```bash
curl -X POST http://localhost:8000/incident/fix \
  -H "Content-Type: application/json" \
  -d '{
    "incident_id": "replace-with-incident-id",
    "action_taken": "Restarted payment-service and rolled back the canary",
    "actor": "oncall-engineer",
    "result": "Success",
    "feedback": "Resolved",
    "notes": "Error rate dropped and latency recovered",
    "final_resolution": true
  }'
```

## Frontend Notes

The frontend API layer is in [frontend/src/services/api.ts](/Users/nikhiljuluri/Desktop/BugOrbit1/frontend/src/services/api.ts). It currently calls:

- `POST /analyze`
- `GET /incident/state`
- `POST /incident/fix`

The main UI state and views are managed from [frontend/src/App.tsx](/Users/nikhiljuluri/Desktop/BugOrbit1/frontend/src/App.tsx), which includes:

- incident pipeline stages
- navigation for live and resolved incidents
- graph exploration
- simulation flows
- fix entry
- recommendation display

## Configuration Notes

Backend configuration is loaded through `pydantic-settings` in [backend/app/core/config.py](/Users/nikhiljuluri/Desktop/BugOrbit1/backend/app/core/config.py).

Important runtime settings:

- `NEO4J_ENABLED`
- `NEO4J_URI`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`
- `NEO4J_DATABASE`
- `OPENAI_MODEL`
- `OPENAI_API_KEY`
- `VECTOR_TOP_K`

One naming detail to keep in mind: the repository and product docs use the name `BugOrbit`, while some backend and frontend strings still use `RocketRide AI` as an internal app label. That is expected in the current codebase.

## CI

GitHub Actions workflow:

- [.github/workflows/ci.yml](/Users/nikhiljuluri/Desktop/BugOrbit1/.github/workflows/ci.yml)

The workflow currently validates:

- backend dependency installation
- backend compile sanity
- frontend dependency installation
- frontend production build

## Deployment Guidance

For a lightweight production setup, a reasonable split is:

- frontend on Vercel or Netlify
- backend on Render, Railway, Fly.io, or another FastAPI-friendly host
- graph database on Neo4j Aura or a self-hosted Neo4j instance

Minimum deployment checklist:

1. set backend environment variables in your hosting platform
2. provide a reachable `NEO4J_URI`
3. add `OPENAI_API_KEY` if using OpenAI-backed reasoning
4. set `VITE_API_BASE_URL` in the frontend deployment
5. verify `/health`, `/analyze`, and `/incident/state` after deployment

## Known Limitations

- runtime incident state is file-backed, which is convenient for demos but not ideal for multi-instance production deployments
- recommendation retrieval uses a lightweight local incident corpus rather than a managed vector service
- there is no authentication or authorization layer on the API or dashboard
- Docker Compose installs dependencies at container startup, which is acceptable for local development but not optimized for production
- some product naming is still mixed between `BugOrbit` and `RocketRide AI`

## Suggested Next Improvements

1. add automated API tests for analysis and incident lifecycle routes
2. move runtime incident state to a persistent database-backed store
3. add auth, audit logging, and role-aware incident actions
4. package the backend into a production-ready image instead of runtime installs
5. create a checked-in `frontend/.env.example`
6. unify product naming across backend metadata, frontend labels, and documentation

## Troubleshooting

### Frontend cannot reach the backend

Check:

- `frontend/.env` exists
- `VITE_API_BASE_URL` points to the correct backend port
- the backend is running on `http://localhost:8000`

### Neo4j-backed graph results look empty

Check:

- `NEO4J_ENABLED=true`
- the configured URI, username, password, and database are valid
- your payload contains multiple services or dependency hints

### Incident state is not updating

Check:

- `/incident/state` returns data
- the analysis request completed successfully
- the runtime state file is writable
- the incident ID used in `/incident/fix` matches an existing active incident

## License

This repository does not currently include a license file. Add one before open-source distribution if you plan to share the code publicly.
