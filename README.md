# Loan Test Case Engine

An AI-powered platform that extracts business rules from BRD documents (PDF/DOCX) and generates test cases with matched loan records from a 100,000-record database.

## What It Does

1. **Upload** a Business Requirements Document (PDF or DOCX)
2. **Extract** structured business rules using AI (OpenAI or Azure OpenAI)
3. **Review & Approve** extracted rules with conflict detection
4. **Generate** test cases across 5 categories (Positive, Negative, Boundary, Edge, Interaction)
5. **Match** customers from the loan records database via JSONB queries
6. **Export** results as CSV or JSON with full request/response payloads

## Core Sections

### 1. BRDs (Business Requirement Documents)
- Upload BRD documents (PDF/DOCX)
- AI extracts business rules automatically
- Review, edit, and approve extracted rules
- Full workflow stepper: Upload → Extract → Approve → Generate → Export

### 2. Loan Records Database
- 100,000 seeded loan records with full `request_payload` and `response_payload` JSON
- PostgreSQL JSONB storage with GIN indexes for fast querying
- Search, filter, view stats, and upload CSV to add more records

### 3. Test Suites & Test Cases
- Generate test cases from approved BRD rules
- 5 categories: POSITIVE, NEGATIVE, BOUNDARY, EDGE, INTERACTION
- Configurable counts per category and max customer matches per test case
- Customer matching via dynamic JSONB queries against the loan records DB
- Export to CSV/JSON with full request/response payloads

## Architecture

```
Frontend (Next.js 16)          Backend (FastAPI)
React 19 + Tailwind CSS 4     BRD Pipeline + Test Case Engine
shadcn/ui + Framer Motion      OpenAI / Azure OpenAI
        │                              │
        └──── REST API (/api/v1) ──────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
   PostgreSQL     Redis      S3/Local
   (JSONB)       (cache)    (uploads)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI, Pydantic, SQLAlchemy (async) |
| AI/LLM | OpenAI GPT-4o or Azure OpenAI |
| Database | PostgreSQL + asyncpg (JSONB with GIN indexes) |
| Cache | Redis |
| Document Parsing | Unstructured, pypdf, python-docx |
| Data Processing | pandas |
| Export | CSV, JSON |
| Frontend | Next.js 16, React 19, TypeScript |
| Styling | Tailwind CSS 4, shadcn/ui, Framer Motion |
| Deployment | Docker Compose |

## Quick Start

### One-Time Setup (New Machine)

Checks prerequisites, starts Postgres + Redis, installs deps, **creates the
full schema (incl. `audit_events` + all migration columns)**, and seeds the
loan corpus.

```bash
# Windows
scripts\setup.bat

# Linux / macOS / WSL
chmod +x scripts/*.sh
./scripts/setup.sh            # override corpus size with SEED_COUNT=10000 ./scripts/setup.sh
```

### Start the Application

```bash
scripts\start.bat     # Windows
./scripts/start.sh    # Linux / macOS / WSL
```

This starts:
- PostgreSQL + Redis (Docker)
- Backend on http://localhost:8001
- Frontend on http://localhost:3000

### Stop the Application

```bash
scripts\stop.bat      # Windows
./scripts/stop.sh     # Linux / macOS / WSL
```

### Manual Setup

**Backend:**

```bash
cd backend
pip install -e ".[dev]"

# Create .env file (see Environment Variables below)

# Create the schema + apply additive migrations (idempotent).
# Required before seeding so every table exists first.
python -m scripts.init_db

# Seed 100K loan records (override: --count=10000)
python -m scripts.seed_loan_records --count=100000

# Start server (also auto-runs create_all + migrations + backfills on startup)
uvicorn app.main:app --reload --port 8001
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

## LLM Provider Configuration

The app supports both **OpenAI** and **Azure OpenAI**. Switch between them via environment variables.

### OpenAI (Default)

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o
```

### Azure OpenAI

```env
LLM_PROVIDER=azure
AZURE_OPENAI_API_KEY=your-azure-api-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-08-01-preview
```

Just change `LLM_PROVIDER` from `openai` to `azure` and fill in the Azure values. No code changes needed.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_PROVIDER` | No | `openai` | LLM provider: `openai` or `azure` |
| `OPENAI_API_KEY` | Yes (if openai) | — | OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o` | OpenAI model name |
| `AZURE_OPENAI_API_KEY` | Yes (if azure) | — | Azure OpenAI API key |
| `AZURE_OPENAI_ENDPOINT` | Yes (if azure) | — | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_DEPLOYMENT` | Yes (if azure) | — | Azure OpenAI deployment name |
| `AZURE_OPENAI_API_VERSION` | No | `2024-08-01-preview` | Azure OpenAI API version |
| `DATABASE_URL` | No | `postgresql+asyncpg://postgres:postgres@localhost:5432/policy_impact_engine` | PostgreSQL connection string |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection URL |
| `MAX_UPLOAD_SIZE_MB` | No | `50` | Max file upload size |

## Pipeline Flow

```
BRD Upload (PDF/DOCX)
  ↓
Parse Document → Extract sections
  ↓
Extract Rules (OpenAI / Azure OpenAI) → Structured JSON with conditions & actions
  ↓
Validate Rules → Conflict detection, completeness checks
  ↓
Human Review → Approve / edit / reject rules
  ↓
Configure Test Counts → Per category + max matches
  ↓
Generate Test Cases → POSITIVE, NEGATIVE, BOUNDARY, EDGE, INTERACTION
  ↓
Match Customers → JSONB queries against 100K loan records
  ↓
Export → CSV / JSON with full request & response payloads
```

## API Endpoints

| Module | Prefix | Purpose |
|--------|--------|---------|
| BRDs | `/api/v1/brds` | Upload and manage BRD documents |
| Rules | `/api/v1/rules` | Extracted business rules management |
| Test Cases | `/api/v1/test-cases` | Generate, list, and export test suites |
| Loan Records | `/api/v1/loan-records` | Browse, search, upload loan data |
| Dashboard | `/api/v1/dashboard` | Aggregated stats |

## Frontend Pages

| Route | Page |
|-------|------|
| `/` | Dashboard with stats cards |
| `/brds` | BRD upload with drag-and-drop |
| `/brds/[id]` | BRD workflow stepper (Extract → Approve → Generate) |
| `/loan-records` | Loan records with stats, search, CSV upload |
| `/loan-records/[id]` | Full loan record detail (request + response payload) |
| `/rules/[ruleSetId]` | Rule approval, test count config, generate test cases |
| `/test-suites` | All test suites with BRD links |
| `/test-suites/[suiteId]` | Test case details with matched customers |

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── api/v1/           # API routers (brds, rules, test_cases, loan_records, dashboard)
│   │   ├── models/           # SQLAlchemy ORM models (JSONB for loan records)
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── services/         # Business logic (test_case_service, customer_matcher, field_registry)
│   │   ├── pipeline/         # BRD processing pipeline
│   │   │   ├── document_parser.py   # PDF/DOCX parsing
│   │   │   ├── rule_extractor.py    # OpenAI / Azure OpenAI extraction
│   │   │   ├── rule_compiler.py     # Rules → executable logic
│   │   │   └── rule_validator.py    # Conflict detection
│   │   └── config.py         # Settings (LLM provider config)
│   ├── scripts/
│   │   └── seed_loan_records.py  # Seed 100K diverse loan records
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js App Router pages
│   │   ├── components/       # React components (shadcn/ui)
│   │   └── lib/              # API client, types, utilities
│   └── package.json
├── scripts/
│   ├── start.bat             # Start all services
│   ├── stop.bat              # Stop all services
│   └── setup.bat             # One-time setup for new machines
└── docker-compose.yml
```

## AWS Deployment

### Low Cost (~$40/mo)
| Component | Service |
|-----------|---------|
| Database | RDS PostgreSQL (db.t4g.micro) |
| Redis | ElastiCache (cache.t4g.micro) |
| Backend | App Runner |
| Frontend | Amplify Hosting |
| Files | S3 |

### Production (~$215/mo)
| Component | Service |
|-----------|---------|
| Database | RDS PostgreSQL (db.t4g.small, Multi-AZ) |
| Redis | ElastiCache (2 nodes) |
| Backend | ECS Fargate (2 tasks) |
| Frontend | S3 + CloudFront |
| Files | S3 |
| Networking | VPC + ALB + NAT Gateway |

## License

Private — all rights reserved.
