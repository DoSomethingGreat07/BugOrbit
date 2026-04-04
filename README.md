# BugOrbit
BugOrbit is a graph-powered incident intelligence platform that turns raw telemetry into structured incidents, impact analysis, Neo4j-backed service graphs, remediation guidance, and live incident lifecycle state. It helps teams detect, investigate, resolve, and learn from production failures faster.

# BugOrbit

BugOrbit is a graph-powered incident intelligence platform for turning raw production telemetry into structured incidents, dependency-aware impact analysis, remediation guidance, and runtime incident lifecycle state.

This repository contains:

- a FastAPI backend that normalizes telemetry, analyzes traces, persists graph context, and tracks incident state
- a React + Vite frontend for live incident monitoring, graph exploration, simulation, and fix recording
- sample incident data and telemetry payloads for local testing
- prompt files for the reasoning agents used by the system

## What BugOrbit does

BugOrbit is built around one core workflow:

1. ingest raw telemetry payloads
2. normalize them into a consistent internal trace schema
3. identify the failure point and likely propagation path
4. query and enrich service relationships in Neo4j
5. build a runtime incident record
6. expose active and resolved incident state to the UI
7. record operator fixes and move incidents from active to resolved

The result is a system where the dashboard is driven by runtime incident state instead of hardcoded counts or mock cards.

## Core capabilities

- Telemetry normalization from loose payloads into strict backend schema objects
- Trace analysis to infer failure point and likely issue cluster
- Graph persistence into Neo4j for services, spans, alerts, incidents, and dependencies
- Runtime incident state for active and resolved incidents
- Similar incident retrieval and fix suggestions from a local corpus
- Frontend views for:
  - active incidents
  - resolved incidents
  - dependency graph exploration
  - telemetry inspection
  - simulation
  - fix entry and incident resolution

## High-level architecture

```text
Telemetry Payload
  -> Normalization
  -> Structured Trace
  -> Failure / Impact Analysis
  -> Neo4j Graph Persistence
  -> Runtime Incident Registration
  -> Frontend Dashboard State
```

### Backend responsibilities

The backend is responsible for:

- accepting telemetry payloads in either strict or loose form
- normalizing fields like `latency_ms`, deployment `timestamp`, sparse alerts, and host signals
- creating structured trace objects
- analyzing the trace and impact path
- syncing services, edges, telemetry, and incidents into Neo4j
- keeping runtime incident state for active and resolved incidents
- recording fix actions and incident resolution

### Frontend responsibilities

The frontend is responsible for:

- sending payloads to the backend
- rendering active and resolved incidents from backend incident state
- showing reasoning, impact, graph, and remediation views
- allowing operators to record fixes and mark incidents resolved
- refreshing the dashboard after incident creation or resolution

## Repository structure

```text
BugOrbit/
├── agents/                  # Prompt and agent support files
├── backend/                 # FastAPI app and backend services
│   ├── app/
│   │   ├── core/            # Settings and config
│   │   ├── db/              # Neo4j and vector store adapters
│   │   ├── models/          # Pydantic schemas
│   │   ├── routes/          # API routes
│   │   └── services/        # Normalization, analysis, orchestration, incident state
│   └── requirements.txt
├── data/
│   └── incidents/           # Sample incidents and runtime incident state
├── frontend/                # React + Vite app
├── docker-compose.yml       # Local backend/frontend/neo4j stack
├── sample.json              # Sample telemetry payload
└── live_telemetry_sample.json
```

## Backend API

The FastAPI app exposes these route groups:

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

- accepts a telemetry payload
- normalizes it into the internal trace schema
- returns a `StructuredTrace`

`POST /analyze`

- accepts a telemetry payload
- normalizes it if needed
- runs the full BugOrbit pipeline
- returns the full incident analysis response

`POST /telemetry/normalize`

- accepts OpenTelemetry-style live telemetry payloads
- adapts them to the internal schema

`POST /telemetry/analyze`

- runs full analysis on adapted live telemetry input

`POST /graph-query`

- queries graph relationships for service impact exploration

`POST /incident/search`

- searches similar incidents from the local incident corpus

`GET /incident/state`

- returns current runtime incident state:
  - active incidents
  - resolved incidents

`POST /incident/fix`

- records a fix for an incident
- optionally marks it resolved
- updates runtime state and graph state

## Incident lifecycle

BugOrbit keeps incident lifecycle in runtime state and syncs that state into Neo4j.

### Incident creation

When a telemetry payload is analyzed:

1. the payload is normalized
2. a structured trace is created
3. the failure point and impact path are computed
4. a runtime incident is created or reopened
5. the incident is persisted to runtime state
6. the incident is synced into Neo4j as an `Incident` node

### Incident resolution

When the user records a fix with final resolution:

1. the fix action is appended to the incident timeline
2. the incident status becomes `resolved`
3. `resolved_at` and resolution metadata are stored
4. Neo4j incident and service state are updated
5. active and resolved counts change automatically
6. the frontend refreshes from backend incident state

## Telemetry normalization

One of the main backend features in this repo is a normalization pipeline that accepts loose telemetry payloads and converts them into strict backend schema objects.

This means payloads can include fields like:

- `latency_ms` instead of `duration_ms`
- deployment `timestamp` instead of `deployed_at`
- `cpu_usage` instead of `cpu_pct`
- sparse alert objects with missing optional fields
- explicit `dependencies`

The backend converts these into internal schema objects such as:

- `Span`
- `LogRecord`
- `MetricRecord`
- `AlertRecord`
- `DeploymentRecord`
- `HostSignalRecord`
- `TraceIngestRequest`

This is the reason the dashboard can be driven from real incident state instead of assuming the input is already perfectly normalized.

## Neo4j graph model

When Neo4j is enabled, BugOrbit persists graph entities such as:

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

### Important relationship types

- `OWNS_TRACE`
- `TOUCHED`
- `HAS_SPAN`
- `EMITTED_SPAN`
- `PARENT_OF`
- `CALLS`
- `DEPENDS_ON`
- `EMITTED_LOG`
- `OBSERVED_METRIC`
- `TRIGGERED_FOR`
- `DEPLOYED_AS`
- `RUNS_ON`
- `HAS_HYPOTHESIS`
- `IMPACTS`
- `SIMILAR_TO`
- `INVOLVES`
- `AFFECTS`
- `ROOT_CAUSE`
- `HAS_FIX_ACTION`

### Graph persistence behavior

The graph is updated in stages:

1. trace ingestion persists services, telemetry records, span structure, and dependencies
2. analysis persists blast radius, hypotheses, and incident linkage
3. runtime incident sync persists active or resolved incident state
4. fix recording persists fix actions and resolution metadata

If Neo4j is unavailable, BugOrbit falls back to an internal dependency map so local development can continue.

## Frontend application

The frontend is a React + Vite application that consumes backend APIs and presents the incident workflow through a dashboard-style interface.

### Main views

- Dashboard
- Live Incidents
- Resolved Incidents
- Dependency Explorer
- Fix Memory
- Telemetry Explorer
- Simulation Lab
- Settings

### Frontend behavior

- active and resolved incident counts are fetched from backend state
- recording a fix calls the backend lifecycle API
- final resolution moves an incident from active to resolved
- graph panels and detail cards update from the current incident source

## Local development

### Prerequisites

- Python 3.12+
- Node.js 20+
- npm
- Neo4j 5.x, or Docker for running the full local stack

## Environment configuration

### Backend

Copy the example file:

```bash
cp backend/.env.example backend/.env
```

Typical backend env values:

```bash
APP_NAME=RocketRide AI
NEO4J_ENABLED=true
NEO4J_URI=bolt://localhost:7687
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

### Frontend

Copy the example file:

```bash
cp frontend/.env.example frontend/.env
```

Frontend env values:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

## Running locally

### Option 1: Run services manually

#### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at:

- `http://localhost:5173`

The backend will be available at:

- `http://localhost:8000`

### Option 2: Run with Docker Compose

```bash
docker compose up --build
```

This starts:

- backend on `http://localhost:8000`
- frontend on `http://localhost:5173`
- Neo4j on:
  - `http://localhost:7474`
  - `bolt://localhost:7687`

## Example payloads

Two useful files are already included:

- [sample.json](/Users/nikhiljuluri/Desktop/BugOrbit1/sample.json)
- [live_telemetry_sample.json](/Users/nikhiljuluri/Desktop/BugOrbit1/live_telemetry_sample.json)

### Analyze a payload

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d @sample.json
```

### Normalize a payload only

```bash
curl -X POST http://localhost:8000/trace \
  -H "Content-Type: application/json" \
  -d @sample.json
```

### Analyze live telemetry

```bash
curl -X POST http://localhost:8000/telemetry/analyze \
  -H "Content-Type: application/json" \
  -d @live_telemetry_sample.json
```

### Read incident runtime state

```bash
curl http://localhost:8000/incident/state
```

## Runtime incident state

BugOrbit stores runtime incident lifecycle data in:

- [runtime_state.json](/Users/nikhiljuluri/Desktop/BugOrbit1/data/incidents/runtime_state.json)

This file is treated as local runtime state and is ignored by Git. It is used to drive:

- active incident counts
- resolved incident counts
- live incident list
- resolved incident list
- incident fix history

## GitHub and deployment readiness

This repository includes deployment-oriented project hygiene:

- `.gitignore` excludes env files, logs, build artifacts, package caches, and runtime incident state
- `.github/workflows/ci.yml` builds backend and frontend on push and pull request
- backend and frontend example env files are included

### Recommended deployment setup

- Frontend: Vercel or Netlify
- Backend: Render, Railway, Fly.io, or any container host for FastAPI
- Graph database: Neo4j Aura or a self-hosted Neo4j instance

### Minimum deployment checklist

1. Configure backend environment variables.
2. Configure `VITE_API_BASE_URL` for the frontend.
3. Point the backend at a reachable Neo4j instance.
4. Store secrets in the deployment platform, not in Git.
5. Confirm `/health`, `/analyze`, and `/incident/state` work in the deployed environment.

## CI

GitHub Actions CI is defined in:

- [.github/workflows/ci.yml](/Users/nikhiljuluri/Desktop/BugOrbit1/.github/workflows/ci.yml)

Current checks:

- backend dependency install
- backend compile validation
- frontend dependency install
- frontend production build

## Known limitations

- The vector incident retrieval layer uses a lightweight local corpus rather than a production vector database.
- Neo4j persistence falls back to demo relationships if the database is unavailable.
- The frontend bundle is large enough to trigger Vite chunk size warnings.
- There is no auth layer yet for the API or dashboard.
- Runtime incident state is file-backed for local development, not yet backed by a production database table.

## Recommended next improvements

1. Add automated API tests for `/analyze`, `/incident/state`, and `/incident/fix`.
2. Replace file-backed runtime incident state with a persistent production store.
3. Add authentication and audit logging.
4. Add background jobs for long-running analysis work.
5. Split the frontend bundle for smaller production assets.
6. Add a first-class deployment recipe for one-click cloud environments.

## Troubleshooting

### Live incident count does not update

Check:

- backend is running the latest code
- `/incident/state` returns data
- the analyzed payload actually creates or reopens an active incident
- the frontend is pointing to the correct `VITE_API_BASE_URL`

### Fix recording hangs

Check:

- backend has been restarted after recent incident-state changes
- `/incident/fix` returns a response
- Neo4j connectivity is not blocking backend writes

### Graph looks sparse

Check:

- Neo4j is enabled
- the payload includes enough services, spans, alerts, or dependencies
- the backend can connect to the configured Neo4j instance

## License and ownership

No explicit license file is included in this repository yet. Add one before public open-source distribution if needed.
