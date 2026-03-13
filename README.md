# Policy Impact Engine

An AI-powered platform that extracts business rules from BRD documents (PDF/DOCX) and simulates their impact on customer-level lending data before production deployment.

## What It Does

1. **Upload** a Business Requirements Document (PDF or DOCX)
2. **Extract** structured business rules using Claude AI via a LangGraph pipeline
3. **Review** extracted rules with conflict detection and human approval
4. **Simulate** rule impact against customer datasets
5. **Compare** scenarios side-by-side with visual dashboards
6. **Export** results as PDF reports or CSV

## Architecture

```
Frontend (Next.js 16)          Backend (FastAPI)
React 19 + Tailwind CSS 4     LangGraph Pipeline + Simulation Engine
Recharts + shadcn/ui           Claude AI Rule Extraction
        │                              │
        └──── REST API (/api/v1) ──────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
   PostgreSQL     Redis      Celery
   (asyncpg)     (broker)   (workers)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI, Pydantic, SQLAlchemy (async) |
| AI/LLM | Anthropic Claude, LangGraph, LangChain |
| Database | PostgreSQL + asyncpg |
| Task Queue | Celery + Redis |
| Document Parsing | Unstructured, pypdf |
| Data Processing | pandas, numpy |
| Reports | ReportLab (PDF), CSV export |
| Frontend | Next.js 16, React 19, TypeScript |
| Styling | Tailwind CSS 4, shadcn/ui |
| Charts | Recharts |
| Deployment | Docker Compose (5 services) |

## Quick Start

### Docker (recommended)

```bash
# Set your Anthropic API key
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# Start all services
docker-compose up

# Seed demo data (optional)
docker exec -it policy-backend python scripts/seed_demo.py
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

### Local Development

**Backend:**

```bash
cd backend
pip install -e ".[dev]"

# Set environment variables
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/policy_engine"
export ANTHROPIC_API_KEY="sk-ant-..."

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── api/v1/           # 8 API routers
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   ├── pipeline/         # LangGraph processing pipeline
│   │   │   ├── graph.py          # Pipeline orchestration
│   │   │   ├── document_parser.py
│   │   │   ├── rule_extractor.py # Claude AI extraction
│   │   │   ├── rule_compiler.py  # Rules → executable Python
│   │   │   └── rule_validator.py # Conflict detection
│   │   ├── simulation/       # Simulation engine
│   │   │   ├── engine.py         # Main runner
│   │   │   ├── baseline.py       # Production rule baseline
│   │   │   └── comparator.py     # Baseline vs simulated
│   │   └── tasks/            # Celery background tasks
│   ├── scripts/              # Seed & demo data generation
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js App Router (12 routes)
│   │   ├── components/       # React components
│   │   └── lib/              # API client, types, utilities
│   └── Dockerfile
└── docker-compose.yml
```

## Pipeline Flow

```
BRD Upload (PDF/DOCX)
  ↓
Parse Document → Extract sections
  ↓
Extract Rules (Claude AI) → Structured JSON with conditions & actions
  ↓
Validate Rules → Conflict detection, completeness checks
  ↓
Human Review → Approve / edit / reject rules
  ↓
Compile Rules → Executable Python objects
  ↓
Run Simulation → Apply against customer dataset
  ↓
Compare Results → Baseline vs simulated metrics
  ↓
Export → PDF report, CSV data
```

## API Endpoints

| Module | Prefix | Purpose |
|--------|--------|---------|
| BRDs | `/api/v1/brds` | Upload and manage BRD documents |
| Datasets | `/api/v1/datasets` | Upload customer CSV/JSON data |
| Rules | `/api/v1/rules` | CRUD for extracted business rules |
| Simulations | `/api/v1/simulations` | Create and manage simulations |
| Scenarios | `/api/v1/scenarios` | Compare multiple simulations |
| Pipeline | `/api/v1/pipeline` | Trigger end-to-end BRD processing |
| Export | `/api/v1/export` | PDF and CSV report generation |
| Dashboard | `/api/v1/dashboard` | Aggregated analytics |

## Frontend Pages

| Route | Page |
|-------|------|
| `/` | Dashboard with stats and recent simulations |
| `/brds` | BRD upload with drag-and-drop |
| `/brds/[id]` | BRD detail with pipeline trigger |
| `/datasets` | Dataset upload and management |
| `/datasets/[id]` | Data profiling (schema, stats, sample) |
| `/rules/[ruleSetId]` | Rule editor with conflict detection |
| `/simulations` | Simulation list |
| `/simulations/new` | New simulation form |
| `/simulations/[id]` | Impact dashboard with charts |
| `/scenarios` | Scenario comparison |
| `/scenarios/[id]` | Side-by-side simulation comparison |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Claude API key for rule extraction |
| `DATABASE_URL` | Yes | — | PostgreSQL connection string |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis for Celery broker |
| `MAX_UPLOAD_SIZE_MB` | No | `50` | Max file upload size |
| `UPLOAD_DIR` | No | `./uploads` | File storage directory |

## License

Private — all rights reserved.
