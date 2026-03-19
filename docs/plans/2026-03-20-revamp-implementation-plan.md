# Loan Test Case Engine Revamp — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Revamp the app to BRD→Rules→Test Cases with loan DB customer matching, removing simulation/dataset/scenario features.

**Architecture:** PostgreSQL JSONB for loan records, existing BRD/rule extraction kept, new test case generator that builds filter conditions from rules and queries the loan DB for matching customers. Frontend simplified to 3 sections: BRDs, Loan Records, Test Suites.

**Tech Stack:** Python/FastAPI, PostgreSQL JSONB, SQLAlchemy async, Next.js 16, shadcn/ui, Tailwind

---

### Task 1: Clean Up — Remove Deprecated Backend Code

**Files:**
- Delete: `backend/app/models/dataset.py`
- Delete: `backend/app/models/simulation.py`
- Delete: `backend/app/api/v1/datasets.py`
- Delete: `backend/app/api/v1/simulations.py`
- Delete: `backend/app/api/v1/scenarios.py`
- Delete: `backend/app/api/v1/pipeline.py`
- Delete: `backend/app/api/v1/export.py`
- Delete: `backend/app/services/dataset_service.py`
- Delete: `backend/app/services/simulation_service.py`
- Delete: `backend/app/services/scenario_service.py`
- Delete: `backend/app/services/export_service.py`
- Delete: `backend/app/services/pdf_report.py`
- Delete: `backend/app/services/column_detector.py`
- Delete: `backend/app/simulation/` (entire directory)
- Delete: `backend/app/tasks/` (entire directory)
- Delete: `backend/app/pipeline/test_case_generator.py`
- Delete: `backend/app/pipeline/graph.py`
- Delete: `backend/app/pipeline/schemas.py`
- Modify: `backend/app/main.py` — remove imports/routers for datasets, simulations, scenarios, pipeline, export
- Modify: `backend/app/models/__init__.py` — remove Dataset, Simulation, SimulationResult, Scenario imports
- Modify: `backend/app/services/__init__.py` — remove deleted service imports

**Step 1:** Delete all files listed above.

**Step 2:** Update `backend/app/main.py`:
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.api.v1.brds import router as brds_router
from app.api.v1.rules import router as rules_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.test_cases import router as test_cases_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    import app.models.brd
    import app.models.rule
    import app.models.test_case
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="Policy Impact Engine", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(brds_router, prefix="/api/v1")
app.include_router(rules_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(test_cases_router, prefix="/api/v1")

@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Step 3:** Update `backend/app/models/__init__.py`:
```python
from app.models.brd import BrdDocument, FileType
from app.models.rule import RuleSet, Rule, RuleSetStatus, RuleType
from app.models.test_case import TestCaseSuite, TestCase, TestCaseCategory

__all__ = [
    "BrdDocument", "FileType",
    "RuleSet", "Rule", "RuleSetStatus", "RuleType",
    "TestCaseSuite", "TestCase", "TestCaseCategory",
]
```

**Step 4:** Verify backend starts: `cd backend && python -m uvicorn app.main:app --port 8001`

**Step 5:** Commit:
```bash
git add -A && git commit -m "refactor: remove deprecated simulation/dataset/scenario code"
```

---

### Task 2: Clean Up — Remove Deprecated Frontend Code

**Files:**
- Delete: `frontend/src/app/datasets/` (entire directory)
- Delete: `frontend/src/app/simulations/` (entire directory)
- Delete: `frontend/src/app/scenarios/` (entire directory)
- Delete: `frontend/src/components/datasets/` (entire directory)
- Delete: `frontend/src/components/simulations/` (entire directory)
- Delete: `frontend/src/components/scenarios/` (entire directory)
- Delete: `frontend/src/components/impact/` (entire directory)
- Delete: `frontend/src/components/dashboard/recent-simulations.tsx`
- Delete: `frontend/src/components/dashboard/impact-chart.tsx`
- Modify: `frontend/src/components/sidebar.tsx` — update nav items
- Modify: `frontend/src/lib/types.ts` — remove Dataset, Simulation, SimulationResult, Scenario interfaces

**Step 1:** Delete all files/directories listed above.

**Step 2:** Update sidebar nav items in `frontend/src/components/sidebar.tsx`:
```typescript
const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard, color: "text-blue-500" },
  { href: "/brds", label: "BRDs", icon: FileText, color: "text-blue-500" },
  { href: "/loan-records", label: "Loan Records", icon: Database, color: "text-emerald-500" },
  { href: "/test-suites", label: "Test Suites", icon: FlaskConical, color: "text-pink-500" },
];
```
Also update the subtitle from "Simulation Engine" to "Test Case Engine".

**Step 3:** Clean up `frontend/src/lib/types.ts` — remove `Dataset`, `Simulation`, `SimulationResult`, `Scenario`, `ImpactSummary` interfaces. Keep `BrdDocument`, `BrdWorkflow`, `RuleSet`, `Rule`, `TestCase`, `TestCaseSuite`.

**Step 4:** Verify frontend builds: `cd frontend && npm run build`

**Step 5:** Commit:
```bash
git add -A && git commit -m "refactor: remove deprecated frontend pages and components"
```

---

### Task 3: Create Loan Record Model + Schema + Seeder

**Files:**
- Create: `backend/app/models/loan_record.py`
- Create: `backend/app/schemas/loan_record.py`
- Create: `backend/app/services/loan_record_service.py`
- Create: `backend/scripts/seed_loan_records.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/main.py` — import model for table creation

**Step 1:** Create `backend/app/models/loan_record.py`:
```python
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class LoanRecord(Base):
    __tablename__ = "loan_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    loan_application_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    request_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    response_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_loan_records_request_gin", "request_payload", postgresql_using="gin"),
        Index("idx_loan_records_response_gin", "response_payload", postgresql_using="gin"),
    )
```

**Step 2:** Create `backend/app/schemas/loan_record.py`:
```python
from pydantic import BaseModel


class LoanRecordResponse(BaseModel):
    id: str
    loan_application_id: str
    request_payload: dict
    response_payload: dict
    created_at: str

    model_config = {"from_attributes": True}


class LoanRecordListResponse(BaseModel):
    id: str
    loan_application_id: str
    decision_status: str | None = None
    bureau_score: int | None = None
    monthly_income: float | None = None
    desired_amount: float | None = None
    created_at: str

    model_config = {"from_attributes": True}


class LoanRecordStatsResponse(BaseModel):
    total_records: int
    decision_distribution: dict
    bureau_score_range: dict
    income_range: dict


class LoanRecordUploadResponse(BaseModel):
    imported: int
    skipped: int
    errors: int
```

**Step 3:** Create `backend/app/services/loan_record_service.py` with CRUD functions:
- `list_loan_records(db, limit, offset, filters)` — paginated list with optional JSONB filters
- `get_loan_record(id, db)` — single record
- `get_stats(db)` — aggregate stats
- `bulk_import(records, db)` — import from parsed CSV/JSON
- `query_by_filters(filters, db, limit)` — JSONB filter query for test case matching

**Step 4:** Create `backend/scripts/seed_loan_records.py` — generates 2000+ synthetic records with:
- Realistic distributions (bureau scores normal ~700, income log-normal, etc.)
- Correlated fields (higher income → higher amounts, better scores → lower rates)
- Full request_payload and response_payload matching the provided JSON structures
- Decision statuses: APPROVED (45%), APPROVED_WITH_CONDITIONS (30%), REJECTED (25%)
- Multiple offer choices for approved applications

**Step 5:** Update `backend/app/models/__init__.py` — add `LoanRecord` import.

**Step 6:** Update `backend/app/main.py` — add `import app.models.loan_record` in lifespan.

**Step 7:** Verify: start backend, run seeder script, check DB has 2000+ records.

**Step 8:** Commit:
```bash
git add -A && git commit -m "feat: add loan record model, schema, service, and seeder"
```

---

### Task 4: Create Loan Records API Router

**Files:**
- Create: `backend/app/api/v1/loan_records.py`
- Modify: `backend/app/main.py` — register router

**Step 1:** Create `backend/app/api/v1/loan_records.py`:
- `GET /loan-records` — paginated list with query params for filtering (bureau_score_min, income_min, etc.)
- `GET /loan-records/stats` — aggregate stats
- `GET /loan-records/{id}` — single record detail
- `POST /loan-records/upload` — CSV bulk import endpoint
- `POST /loan-records/seed` — trigger seeder

**Step 2:** Register in `main.py`:
```python
from app.api.v1.loan_records import router as loan_records_router
app.include_router(loan_records_router, prefix="/api/v1")
```

**Step 3:** Verify: `curl http://localhost:8001/api/v1/loan-records/stats`

**Step 4:** Commit:
```bash
git add -A && git commit -m "feat: add loan records API with list, detail, upload, stats"
```

---

### Task 5: Create Field Registry + JSON Path Mapper

**Files:**
- Create: `backend/app/services/field_registry.py`
- Test: `backend/tests/services/test_field_registry.py`

**Step 1:** Create `backend/app/services/field_registry.py`:
```python
"""Maps rule field names to JSON paths in the loan record request_payload."""

# Manual registry for known field aliases
FIELD_REGISTRY: dict[str, str] = {
    # Direct fields
    "desired_amount": "desired_amount",
    "application_type": "application_type",

    # Customer inputs
    "age": "borrower_credit_model.customer_inputs.age",
    "monthly_income": "borrower_credit_model.customer_inputs.monthly_income",
    "employment_type": "borrower_credit_model.customer_inputs.employment_type",
    "employer_type": "borrower_credit_model.customer_inputs.employer_type",
    "employment_tenure_months": "borrower_credit_model.customer_inputs.employment_tenure_months",
    "residence_type": "borrower_credit_model.customer_inputs.residence_type",
    "city_tier": "borrower_credit_model.customer_inputs.city_tier",
    "dependents": "borrower_credit_model.customer_inputs.dependents",

    # Banking inputs
    "average_monthly_balance_6m": "borrower_credit_model.banking_inputs.average_monthly_balance_6m",
    "cheque_bounces_6m": "borrower_credit_model.banking_inputs.cheque_bounces_6m",
    "emi_obligation_amount": "borrower_credit_model.banking_inputs.emi_obligation_amount",
    "loan_repayment_bounces_12m": "borrower_credit_model.banking_inputs.loan_repayment_bounces_12m",

    # Bureau
    "bureau_score": "borrower_credit_model.bureau_credits.bureau_score",
    "active_loans": "borrower_credit_model.bureau_credits.active_loans",
    "credit_utilization_ratio": "borrower_credit_model.bureau_credits.credit_utilization_ratio",
    "overdue_accounts": "borrower_credit_model.bureau_credits.overdue_accounts",
    "max_dpd_last_12m": "borrower_credit_model.bureau_credits.max_dpd_last_12m",
    "inquiries_last_3m": "borrower_credit_model.bureau_credits.inquiries_last_3m",

    # Calculated attributes
    "dti_ratio": "calculated_attributes.debt_to_income_ratio",
    "debt_to_income_ratio": "calculated_attributes.debt_to_income_ratio",
    "net_monthly_surplus": "calculated_attributes.net_monthly_surplus",
    "banking_stability_index": "calculated_attributes.banking_stability_index",
    "credit_risk_band": "calculated_attributes.credit_risk_band",
    "income_stability_score": "calculated_attributes.income_stability_score",
    "g5_score": "calculated_attributes.scores.g5.score",
    "g6_score": "calculated_attributes.scores.g6.score",
}


def resolve_field_path(field_name: str) -> str | None:
    """Resolve a rule field name to its JSON path in request_payload."""
    normalized = field_name.lower().strip().replace(" ", "_")
    return FIELD_REGISTRY.get(normalized)


def json_path_to_sql(json_path: str) -> str:
    """Convert a dot-separated JSON path to PostgreSQL JSONB accessor.

    Example: 'borrower_credit_model.bureau_credits.bureau_score'
    Returns: "request_payload->'borrower_credit_model'->'bureau_credits'->>'bureau_score'"
    """
    parts = json_path.split(".")
    if len(parts) == 1:
        return f"request_payload->>'{parts[0]}'"
    arrows = "->".join(f"'{p}'" for p in parts[:-1])
    return f"request_payload->{arrows}->>'{parts[-1]}'"


def auto_discover_fields(sample_payload: dict, prefix: str = "") -> dict[str, str]:
    """Walk a JSON payload and register all leaf fields."""
    discovered = {}
    for key, value in sample_payload.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            discovered.update(auto_discover_fields(value, path))
        else:
            leaf_name = key.lower()
            if leaf_name not in FIELD_REGISTRY:
                discovered[leaf_name] = path
    return discovered
```

**Step 2:** Write tests for resolve, json_path_to_sql, and auto_discover.

**Step 3:** Run tests: `cd backend && python -m pytest tests/services/test_field_registry.py -v`

**Step 4:** Commit:
```bash
git add -A && git commit -m "feat: add field registry for rule-to-JSON path mapping"
```

---

### Task 6: Revamp Test Case Generator for Loan DB Matching

**Files:**
- Create: `backend/app/pipeline/test_case_generator.py` (rewrite)
- Create: `backend/app/services/customer_matcher.py`
- Modify: `backend/app/models/test_case.py` — add filter_logic, matched_loan_ids columns; remove inputs column
- Modify: `backend/app/schemas/test_case.py` — update schemas

**Step 1:** Update `backend/app/models/test_case.py`:
- Replace `inputs: Mapped[dict]` with `filter_logic: Mapped[dict]` (JSONB)
- Add `matched_loan_ids: Mapped[list]` (JSONB, default=[])
- Add `match_count: Mapped[int]` (Integer, default=0)

**Step 2:** Update `backend/app/schemas/test_case.py`:
- Update `TestCaseResponse` to include filter_logic, matched_loan_ids, match_count
- Add `TestCaseGenerateRequest` with configurable counts per category:
```python
class TestCaseGenerateRequest(BaseModel):
    rule_set_id: str
    positive_count: int = 3
    negative_count: int = 3
    boundary_count: int = 5
    edge_count: int = 3
    interaction_count: int = 2
```

**Step 3:** Rewrite `backend/app/pipeline/test_case_generator.py`:
- Generate test cases from rules using the field registry to build filter_logic
- Each test case has filter_logic: list of `{"field": "bureau_score", "path": "borrower_credit_model.bureau_credits.bureau_score", "operator": ">=", "value": 700}`
- Uses configurable counts per category
- Does NOT run simulation — just creates filter conditions

**Step 4:** Create `backend/app/services/customer_matcher.py`:
- `match_customers(filter_logic: list[dict], db: AsyncSession, limit: int = 10) -> list[dict]`
- Builds raw SQL JSONB query from filter_logic
- Returns matching loan records with match_reason
- Ranks by proximity to boundary values

**Step 5:** Verify with tests.

**Step 6:** Commit:
```bash
git add -A && git commit -m "feat: revamp test case generator with loan DB customer matching"
```

---

### Task 7: Revamp Test Cases API

**Files:**
- Modify: `backend/app/api/v1/test_cases.py` — rewrite endpoints
- Modify: `backend/app/services/test_case_service.py` — rewrite

**Step 1:** Rewrite `backend/app/services/test_case_service.py`:
- `generate_and_save(rule_set_id, rules, counts, db)` — generate test cases, match customers, persist
- `get_suite(suite_id, db)` — with eagerly loaded test cases and matched customer data
- `list_suites(db)` — all suites with rule set names
- `export_suite(suite_id, format, db)` — CSV or JSON export with matched customers
- `export_by_brd(brd_id, format, db)` — aggregate export across all rule sets for a BRD

**Step 2:** Rewrite `backend/app/api/v1/test_cases.py`:
- `POST /test-cases/generate` — accepts `TestCaseGenerateRequest` with configurable counts
- `GET /test-cases` — list all suites
- `GET /test-cases/{suite_id}` — suite detail with test cases + matched customers
- `GET /test-cases/{suite_id}/export/{format}` — export (csv/json)
- `GET /test-cases/by-brd/{brd_id}/export/{format}` — BRD-level export
- `DELETE /test-cases/{suite_id}` — delete suite

**Step 3:** Verify: generate test cases via API, check matched customers are returned.

**Step 4:** Commit:
```bash
git add -A && git commit -m "feat: revamp test cases API with customer matching and export"
```

---

### Task 8: Update Dashboard

**Files:**
- Modify: `backend/app/services/dashboard_service.py` — update stats
- Modify: `backend/app/api/v1/dashboard.py` — update response
- Modify: `frontend/src/app/page.tsx` — update dashboard
- Modify: `frontend/src/components/dashboard/stats-cards.tsx` — update cards
- Modify: `frontend/src/components/dashboard/quick-actions.tsx` — update actions

**Step 1:** Update dashboard service to return: BRD count, rule set count, test suite count, loan record count. Remove simulation/scenario stats.

**Step 2:** Update frontend dashboard page — remove simulation/impact references, add loan record stats.

**Step 3:** Verify: dashboard loads with correct stats.

**Step 4:** Commit:
```bash
git add -A && git commit -m "feat: update dashboard for revamped app"
```

---

### Task 9: Create Loan Records Frontend Pages

**Files:**
- Create: `frontend/src/app/loan-records/page.tsx` — list page with search/filter/upload
- Create: `frontend/src/app/loan-records/[id]/page.tsx` — detail page with JSON viewer
- Create: `frontend/src/components/loan-records/loan-record-table.tsx` — table component
- Create: `frontend/src/components/loan-records/json-viewer.tsx` — collapsible JSON tree
- Create: `frontend/src/components/loan-records/upload-csv.tsx` — CSV upload form
- Modify: `frontend/src/lib/types.ts` — add LoanRecord interfaces

**Step 1:** Add TypeScript interfaces:
```typescript
export interface LoanRecord {
  id: string;
  loan_application_id: string;
  request_payload: Record<string, any>;
  response_payload: Record<string, any>;
  created_at: string;
}

export interface LoanRecordListItem {
  id: string;
  loan_application_id: string;
  decision_status: string | null;
  bureau_score: number | null;
  monthly_income: number | null;
  desired_amount: number | null;
  created_at: string;
}

export interface LoanRecordStats {
  total_records: number;
  decision_distribution: Record<string, number>;
  bureau_score_range: { min: number; max: number; avg: number };
  income_range: { min: number; max: number; avg: number };
}
```

**Step 2:** Create list page with:
- Stats panel at top (total records, decision distribution)
- Search by loan_application_id
- Filter dropdowns (bureau score range, income range, decision status)
- Paginated table showing key fields
- Upload CSV button

**Step 3:** Create detail page with:
- Header: loan_application_id, decision status badge
- Two tabs: Request Payload (input), Response Payload (output)
- Collapsible JSON tree viewer for each

**Step 4:** Verify: page loads, shows seeded records, search/filter works.

**Step 5:** Commit:
```bash
git add -A && git commit -m "feat: add loan records frontend with browse, filter, upload"
```

---

### Task 10: Create Test Suites Frontend Pages

**Files:**
- Modify: `frontend/src/app/test-cases/page.tsx` → rename to `frontend/src/app/test-suites/page.tsx`
- Modify: `frontend/src/app/test-cases/[suiteId]/page.tsx` → move to `frontend/src/app/test-suites/[suiteId]/page.tsx`
- Modify: `frontend/src/components/test-cases/test-case-table.tsx` — add matched customers column
- Modify: `frontend/src/components/test-cases/test-case-export-panel.tsx` — add BRD-level export
- Create: `frontend/src/components/test-cases/matched-customers-panel.tsx` — expandable customer list

**Step 1:** Move test-cases routes to test-suites for clearer naming.

**Step 2:** Update test case table to show:
- Filter logic (human-readable)
- Matched customer count
- Expandable row showing matched customers with loan_application_id, key fields, match_reason

**Step 3:** Add matched customers panel — when a test case row is expanded, show the matched customers table with:
- loan_application_id (linked to detail page)
- Key input fields that matched
- match_reason

**Step 4:** Add BRD-level export button on suite list page.

**Step 5:** Update export panel to include both suite-level and BRD-level exports.

**Step 6:** Verify: test suites page loads, shows matched customers, exports work.

**Step 7:** Commit:
```bash
git add -A && git commit -m "feat: revamp test suites frontend with matched customers"
```

---

### Task 11: Update BRD Workflow Stepper

**Files:**
- Modify: `frontend/src/components/brds/workflow-stepper.tsx` — update steps
- Modify: `frontend/src/app/brds/[id]/page.tsx` — update workflow flow
- Modify: `frontend/src/app/rules/[ruleSetId]/page.tsx` — update to show test case generation with count config

**Step 1:** Update workflow stepper steps:
1. Upload BRD ✓
2. Extract Rules
3. Review & Approve Rules
4. Generate Test Cases (with configurable counts per category)
5. Export / Download

Remove simulation step entirely.

**Step 2:** On rules page, after approval:
- Show count configuration form (POSITIVE: 3, NEGATIVE: 3, BOUNDARY: 5, EDGE: 3, INTERACTION: 2)
- "Generate Test Cases" button
- After generation: show test case summary + link to test suite detail
- Export buttons (CSV/JSON)

**Step 3:** On BRD detail page:
- Update workflow state handling to skip simulation
- After test cases generated, show export options

**Step 4:** Verify full flow: upload BRD → extract → approve → configure counts → generate → view matched customers → export.

**Step 5:** Commit:
```bash
git add -A && git commit -m "feat: update BRD workflow for test case generation flow"
```

---

### Task 12: Update Frontend Types + Clean Up

**Files:**
- Modify: `frontend/src/lib/types.ts` — final cleanup
- Modify: `frontend/src/lib/api.ts` — verify base URL

**Step 1:** Final types cleanup — ensure only used interfaces remain.

**Step 2:** Update BrdWorkflow interface to remove simulation references, add test case suite info.

**Step 3:** Verify full build: `cd frontend && npm run build` — zero errors.

**Step 4:** Commit:
```bash
git add -A && git commit -m "chore: clean up frontend types and remove unused code"
```

---

### Task 13: Seed Database + End-to-End Verification

**Files:**
- No new files

**Step 1:** Drop old tables from PostgreSQL that are no longer in models:
```sql
DROP TABLE IF EXISTS simulation_results, simulations, scenarios, datasets CASCADE;
```

**Step 2:** Run seeder: `cd backend && python scripts/seed_loan_records.py`

**Step 3:** Verify end-to-end:
1. Open dashboard — shows correct stats (BRDs, loan records, test suites)
2. Upload a BRD → extract rules → approve → generate test cases with custom counts
3. View test suite — test cases with matched customers
4. Export as CSV and JSON — verify format matches design
5. Browse loan records — search, filter, view detail
6. BRD-level export — aggregate test cases across rule sets

**Step 4:** Final commit:
```bash
git add -A && git commit -m "feat: complete revamp — loan test case engine v0.2.0"
git push
```
