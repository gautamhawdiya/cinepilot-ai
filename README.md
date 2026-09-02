# CinePilot AI

**CinePilot takes a screenplay and turns it into actionable, research-grounded
production decisions and production-ready artifacts.**

A filmmaker uploads a screenplay PDF. A staged pipeline of Google ADK agents
running on Gemini — grounded in live, cited web research from
[Parallel](https://parallel.ai) — turns it into a validated screenplay
breakdown, a preliminary budget, a real-world production research brief, an
evidence-backed production plan, a shot-by-shot storyboard, and an
operational call sheet with a downloadable PDF.

```
Screenplay
    ↓  script_agent (Gemini 2.5 Flash)
Screenplay Analysis
    ↓  budget_agent                         production_research_agent
Budget Analysis                    ∥         (Parallel Search tool)
    ↓                                             ↓
    └──────────────────┬─── Production Research ──┘
                        ↓  production_plan_agent
                Production Plan
                        ↓  storyboard_agent
                    Storyboard
                        ↓  call_sheet_agent
                    Call Sheet
                        ↓  deterministic ReportLab render
              Call Sheet PDF / Production Package
```

Every agent output is validated against a Pydantic schema before it becomes
part of the project's persisted state — an agent producing malformed or
schema-invalid JSON fails that project's pipeline run rather than silently
becoming "the truth."

## Why Parallel matters here

Production research isn't a decorative widget — it's a load-bearing input.
`production_research_agent` calls Parallel's live search API as an ADK tool
to find real, current, cited information about filming permits, location
access, equipment restrictions, and safety requirements relevant to the
screenplay's actual locations. Downstream agents (`production_plan_agent`,
`call_sheet_agent`) are explicitly instructed to only use prices and claims
that trace back to that research, and to mark anything requiring local
verification rather than presenting it as settled fact. The frontend surfaces
each finding's confidence, source link, and verification requirement so a
judge can see the research → decision chain directly.

## Architecture

- **Backend**: FastAPI (`api/`). Uploading a screenplay creates a
  project-scoped workspace at `outputs/projects/{project_id}/`; running the
  pipeline is a background `asyncio` task, so the HTTP request returns
  immediately and the frontend polls `/status` for progress.
- **Agents**: Google ADK `Agent`/`LlmAgent` definitions, one per pipeline
  stage, under `agents/` — each wraps a Gemini 2.5 Flash call with a
  schema-constrained `output_schema` and a strict instruction prompt (e.g.
  the storyboard and call sheet agents are explicitly forbidden from
  inventing characters, locations, dates, or story events not present in the
  screenplay).
- **Schemas**: Pydantic models under `schemas/` are the single source of
  truth for every stage's shape (`ScreenplayAnalysis`, `BudgetAnalysis`,
  `ProductionResearch`, `ProductionPlan`, `Storyboard`, `CallSheet`). The API
  layer validates against these before persisting or serving anything.
- **Tools**: `tools/parallel_search.py` is the ADK tool the research agent
  calls into Parallel's live search API.
- **PDF**: `pdf/call_sheet_pdf.py` deterministically renders a validated
  `CallSheet` into a multi-page call sheet PDF with ReportLab — no LLM call.
- **Frontend**: React + TypeScript + Vite (`frontend/`) — single-page
  production workspace: upload → pipeline progress → tabs for Screenplay
  Analysis, Budget, Research, Production Plan, Storyboard, and Call Sheet.

## What's real vs. what's honestly labeled as planning-only

- The storyboard stage produces **shot planning data** (camera angles,
  composition, lighting, an image-generation prompt per shot) — it does not
  generate actual images as part of the live pipeline, and the frontend
  labels it "Planning data" rather than showing a fabricated image.
  `tools/image_generation.py` and `scripts/generate_all_storyboards.py` are
  a separate, manual, Gemini-image CLI utility (writing to a
  non-project-scoped `outputs/storyboards/`) that can render those prompts
  into images offline; wiring that into the live per-project pipeline would
  be a reasonable next step but is out of scope for this submission.
- Research findings that require local verification are labeled as such,
  end to end — the call sheet agent is instructed to turn them into
  verification action items ("Confirm with the selected station operator...")
  rather than asserting them as universal rules.

## Project structure

```
agents/                 Google ADK agent definitions (one per stage)
api/                    FastAPI app, routes, pipeline orchestration, schemas
pdf/                    Deterministic CallSheet -> PDF renderer
schemas/                Canonical Pydantic schemas for every stage's output
tools/                  ADK tools (Parallel search) and the offline image-gen utility
validators/             Extra call-sheet quality checks (not yet wired into the pipeline)
scripts/                Standalone CLI utilities for exercising one agent/tool at a time
                         against test_data/ fixtures — useful for debugging a single
                         stage without running the whole API server
test_data/              Sample screenplay PDF and sample stage outputs used by scripts/
tests/                  Automated test suite (see Testing, below)
frontend/               React + TypeScript + Vite production workspace UI
outputs/projects/{id}/  Per-project generated artifacts (gitignored beyond history)
```

## Local setup

### Prerequisites

- Python 3.12+
- Node.js 20+
- A Gemini API key ([Google AI Studio](https://aistudio.google.com/apikey)),
  or a Google Cloud project with Vertex AI enabled
- A [Parallel](https://parallel.ai) API key

### Environment variables

Copy `.env.example` to `.env` in the repo root and fill in real values (this
file is gitignored — never commit it):

| Variable | Purpose |
|---|---|
| `GOOGLE_API_KEY` | Gemini access via AI Studio (simplest for local dev) |
| `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `GOOGLE_GENAI_USE_ENTERPRISE` | Alternative to the above: route Gemini calls through Vertex AI instead of an API key |
| `PARALLEL_API_KEY` | Required by the production research agent's Parallel Search tool |
| `CORS_ALLOWED_ORIGINS` | Comma-separated list of origins allowed to call the API. Defaults to the local Vite dev server when unset |

The frontend has its own `.env.example` in `frontend/` (`VITE_API_BASE_URL`,
defaults to `http://127.0.0.1:8000`).

### Run the backend

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
uvicorn api.main:app --reload
```

The API serves on `http://127.0.0.1:8000`. Interactive docs at `/docs`.

### Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open the printed local URL (Vite default: `http://localhost:5173`).

### Run a sample screenplay end to end

With both servers running, upload `test_data/sample_screenplay.pdf` through
the UI, or drive it directly against the API:

```bash
curl -F "screenplay=@test_data/sample_screenplay.pdf" http://127.0.0.1:8000/api/projects
# -> {"project_id": "proj_xxxx", ...}
curl -X POST http://127.0.0.1:8000/api/projects/proj_xxxx/run
curl http://127.0.0.1:8000/api/projects/proj_xxxx/status   # poll until "completed" or "failed"
```

Individual agents/tools can also be exercised in isolation via the scripts
in `scripts/` (e.g. `python scripts/test_production_research.py`), which is
useful when iterating on one agent's prompt without running the full API
pipeline.

## Expected outputs

A completed project directory (`outputs/projects/{project_id}/`) contains:

```
project_state.json         Pipeline/stage status, title, error (if any)
screenplay_analysis.json   ScreenplayAnalysis
budget_analysis.json       BudgetAnalysis
production_research.json   ProductionResearch (Parallel-sourced findings)
production_plan.json       ProductionPlan
storyboard.json            Storyboard (shot planning data)
call_sheet.json            CallSheet
call_sheet.pdf             Rendered call sheet PDF
```

## API endpoints

| Method & path | Purpose |
|---|---|
| `POST /api/projects` | Upload a screenplay PDF, create a project |
| `POST /api/projects/{id}/run` | Start the background pipeline |
| `GET /api/projects/{id}` / `/status` | Project state and per-stage status |
| `GET /api/projects/{id}/screenplay` | Screenplay Analysis |
| `GET /api/projects/{id}/budget` | Budget Analysis |
| `GET /api/projects/{id}/research` | Production Research |
| `GET /api/projects/{id}/plan` | Production Plan |
| `GET /api/projects/{id}/storyboard` | Storyboard |
| `GET /api/projects/{id}/call-sheet` | Call Sheet |
| `GET /api/projects/{id}/call-sheet/pdf` | Call Sheet PDF download |
| `GET /health` | Liveness check |

Every per-stage `GET` returns `404` until that stage has completed, and
`500` if the persisted file somehow fails schema validation — a failed or
in-progress stage never silently returns fabricated or partial data.

## Testing

```bash
pip install -r requirements-dev.txt
pytest tests/
```

`tests/test_api_flow.py` covers the full API flow (create → run → poll →
fetch every output → download the PDF) with the single seam that talks to
Gemini/ADK (`pipeline._run_agent`) replaced by canned per-agent responses —
everything else (Pydantic validation, state transitions, file persistence,
FastAPI routing, and the real ReportLab PDF render) runs for real. It also
covers: rejecting non-PDF/empty uploads, 404s for unknown projects and
not-yet-available outputs, two concurrently-run projects never leaking
output into each other's directories, and pipeline failure states (an agent
raising, an agent returning invalid JSON) correctly marking the project and
the *specific* failed stage as failed rather than leaving something stuck at
"running" forever. `tests/test_parallel_search.py` covers the Parallel tool's
result-shaping and its failure mode when no API key is configured, without
making real network calls.

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

## Deployment

The simplest architecture that satisfies the requirements: two stateless
Cloud Run services, one per Dockerfile in this repo.

- **Backend** (`Dockerfile`, repo root): FastAPI + ADK agents. Cloud Run
  injects `$PORT`; the container's `uvicorn` binds to it.
- **Frontend** (`frontend/Dockerfile`): static Vite build served by nginx.
  `VITE_API_BASE_URL` is a **build-time** arg (Vite inlines `VITE_*` vars at
  build time), so point it at the backend's deployed URL when building the
  image.

### Running the images locally

```bash
docker build -t cinepilot-api .
docker build --build-arg VITE_API_BASE_URL=http://127.0.0.1:8090 -t cinepilot-frontend ./frontend

docker run -d --name cinepilot-api -p 8090:8080 \
  --env-file .env \
  -e CORS_ALLOWED_ORIGINS=http://127.0.0.1:8091 \
  cinepilot-api

docker run -d --name cinepilot-frontend -p 8091:8080 cinepilot-frontend
```

Open `http://127.0.0.1:8091`. This works as-is **only if `GOOGLE_API_KEY`
in `.env` is a funded AI Studio key** — the Gemini Developer API path needs
no extra setup. If your org's Cloud project disallows API keys and
requires Application Default Credentials instead (`.env` sets
`GOOGLE_GENAI_USE_ENTERPRISE=True` + `GOOGLE_CLOUD_PROJECT`, which take
precedence over `GOOGLE_API_KEY`), the container needs your host's ADC
mounted in, since Docker doesn't share host `gcloud` credentials
automatically:

```bash
# One-time, on the host: gcloud auth application-default login

docker run -d --name cinepilot-api -p 8090:8080 \
  --env-file .env \
  -e CORS_ALLOWED_ORIGINS=http://127.0.0.1:8091 \
  -e GOOGLE_APPLICATION_CREDENTIALS=/root/.config/gcloud/application_default_credentials.json \
  -v "$env:APPDATA\gcloud\application_default_credentials.json:/root/.config/gcloud/application_default_credentials.json:ro" \
  cinepilot-api
```

(On Cloud Run itself this mount isn't needed — the service automatically
gets ADC from its attached service account.)

```bash
PROJECT=<project>
SA=$(gcloud projects describe $PROJECT --format='value(projectNumber)')-compute@developer.gserviceaccount.com

# One-time setup: enable APIs and grant the default compute service account
# (used by both Cloud Build and Cloud Run here) what it needs.
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  cloudbuild.googleapis.com secretmanager.googleapis.com --project $PROJECT

for ROLE in roles/aiplatform.user roles/artifactregistry.writer \
            roles/storage.objectViewer roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding $PROJECT \
    --member="serviceAccount:$SA" --role="$ROLE" --condition=None
done

gcloud secrets create parallel-api-key --data-file=- --project $PROJECT <<< "$PARALLEL_API_KEY"
gcloud secrets add-iam-policy-binding parallel-api-key --project $PROJECT \
  --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"

# Backend
gcloud run deploy cinepilot-api \
  --source . \
  --project $PROJECT \
  --set-env-vars GOOGLE_CLOUD_PROJECT=$PROJECT,GOOGLE_CLOUD_LOCATION=global,GOOGLE_GENAI_USE_ENTERPRISE=True \
  --set-secrets PARALLEL_API_KEY=parallel-api-key:latest \
  --no-cpu-throttling \
  --allow-unauthenticated

# Frontend (after the backend URL is known)
gcloud auth configure-docker <region>-docker.pkg.dev
docker build --build-arg VITE_API_BASE_URL=https://cinepilot-api-xxxx.a.run.app \
  -t <region>-docker.pkg.dev/$PROJECT/cloud-run-source-deploy/cinepilot-frontend frontend/
docker push <region>-docker.pkg.dev/$PROJECT/cloud-run-source-deploy/cinepilot-frontend
gcloud run deploy cinepilot-frontend \
  --image <region>-docker.pkg.dev/$PROJECT/cloud-run-source-deploy/cinepilot-frontend \
  --project $PROJECT \
  --allow-unauthenticated

# Then update the backend's CORS to allow the frontend's actual URL:
gcloud run services update cinepilot-api --project $PROJECT \
  --update-env-vars CORS_ALLOWED_ORIGINS=https://cinepilot-frontend-xxxx.a.run.app
```

`--no-cpu-throttling` is **required**, not optional: the pipeline runs as a
detached `asyncio.create_task` after `/run` returns, and Cloud Run's default
CPU-throttling-between-requests would otherwise stall it indefinitely
between polls — confirmed by testing (a run sat at `status: created`
forever until this flag was set).

Secrets (`PARALLEL_API_KEY`, and `GOOGLE_API_KEY` if not using Vertex AI via
ADC) belong in **Secret Manager**, referenced with `--set-secrets` — never
baked into the image or committed to the repo. When running on Vertex AI
(the `GOOGLE_CLOUD_PROJECT`/`GOOGLE_GENAI_USE_ENTERPRISE` path), grant the
Cloud Run service account the `roles/aiplatform.user` role instead of
managing a Gemini API key at all.

**Known limitation, stated honestly**: each project's generated artifacts
are written to the container's local filesystem
(`outputs/projects/{id}/`), which is ephemeral on Cloud Run and not shared
across instances. That's fine for a single-instance hackathon demo
(`--max-instances=1`); a durable multi-instance deployment would move
`api/services/project_store.py` and `project_outputs.py` to a shared
backing store (e.g. a GCS bucket) — a deliberately out-of-scope
next step rather than something silently broken today.

## Hackathon technologies

- **Gemini 2.5 Flash** for every content-generation stage (screenplay
  analysis, budget, research, planning, storyboarding, call sheet)
- **Google Agent Development Kit (ADK)** — `Agent`/`LlmAgent` with
  schema-constrained `output_schema`, tool-calling (`parallel_search`), and
  `Runner`/`InMemorySessionService` for execution
- **Parallel** — live web research grounding the production plan and call
  sheet in cited, real-world sources
- **FastAPI** — async API layer with a background-task pipeline
- **Pydantic** — the validation boundary between raw model output and
  authoritative project state
- **React + TypeScript + Vite** — the judge-facing production workspace
- **ReportLab** — deterministic call sheet PDF rendering
- **Cloud Run** — deployment target for both services
