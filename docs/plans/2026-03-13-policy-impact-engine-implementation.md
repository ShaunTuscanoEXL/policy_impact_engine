# Policy Impact Engine - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a standalone platform that parses BRD documents, extracts business rules via LLM, simulates their impact on customer datasets, and produces comparative impact analysis with dashboards.

**Architecture:** FastAPI backend with LangGraph pipeline for AI orchestration, Pandas for simulation, PostgreSQL for persistence. Next.js frontend with Recharts for visualization. Celery+Redis for async jobs.

**Tech Stack:** Python 3.11, FastAPI, LangGraph, LangChain, Anthropic SDK, Pandas, SQLAlchemy, Alembic, Celery, Redis, PostgreSQL, Next.js 14, TypeScript, Recharts, Tailwind CSS, shadcn/ui

---

## Phase 1: Project Scaffolding & Database

### Task 1.1: Backend Project Setup

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`
- Create: `backend/.env.example`

**Step 1: Create backend directory structure**

```bash
mkdir -p backend/app/{api/v1,models,schemas,services,pipeline,simulation,utils}
mkdir -p backend/tests/{api,services,pipeline,simulation}
mkdir -p backend/data/{uploads/brds,uploads/datasets,sample_brds,sample_datasets}
mkdir -p backend/alembic/versions
```

**Step 2: Create pyproject.toml**

```toml
[project]
name = "policy-impact-engine"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "python-multipart>=0.0.9",
    "anthropic>=0.40.0",
    "langgraph>=0.2.0",
    "langchain>=0.3.0",
    "langchain-anthropic>=0.3.0",
    "langchain-community>=0.3.0",
    "unstructured[pdf,docx]>=0.16.0",
    "pandas>=2.2.0",
    "celery[redis]>=5.4.0",
    "redis>=5.0.0",
    "reportlab>=4.2.0",
    "python-docx>=1.1.0",
    "pypdf>=5.0.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=5.0.0",
    "httpx>=0.27.0",
    "ruff>=0.7.0",
]
```

**Step 3: Create app/config.py**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Policy Impact Engine"
    debug: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/policy_impact_engine"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Anthropic
    anthropic_api_key: str = ""

    # File storage
    upload_dir: str = "data/uploads"
    max_upload_size_mb: int = 50

    class Config:
        env_file = ".env"

settings = Settings()
```

**Step 4: Create app/database.py**

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with async_session() as session:
        yield session
```

**Step 5: Create app/main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Policy Impact Engine", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Step 6: Create .env.example**

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/policy_impact_engine
REDIS_URL=redis://localhost:6379/0
ANTHROPIC_API_KEY=your-key-here
```

**Step 7: Install dependencies and verify**

```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
# Verify: GET http://localhost:8000/health returns {"status": "ok"}
```

**Step 8: Commit**

```bash
git add backend/
git commit -m "feat: scaffold backend with FastAPI, config, database setup"
```

---

### Task 1.2: Database Models

**Files:**
- Create: `backend/app/models/brd.py`
- Create: `backend/app/models/rule.py`
- Create: `backend/app/models/dataset.py`
- Create: `backend/app/models/simulation.py`
- Create: `backend/app/models/__init__.py`

**Step 1: Create models/brd.py**

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Enum as SAEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum

class FileType(str, enum.Enum):
    PDF = "PDF"
    DOCX = "DOCX"

class BrdDocument(Base):
    __tablename__ = "brd_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(512))
    file_path: Mapped[str] = mapped_column(String(1024))
    file_type: Mapped[FileType] = mapped_column(SAEnum(FileType))
    parsed_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    rule_sets = relationship("RuleSet", back_populates="brd_document")
```

**Step 2: Create models/rule.py**

```python
import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime, Enum as SAEnum, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class RuleSetStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    REVIEWED = "REVIEWED"
    APPROVED = "APPROVED"
    ARCHIVED = "ARCHIVED"

class RuleType(str, enum.Enum):
    ELIGIBILITY = "ELIGIBILITY"
    PRICING = "PRICING"
    CAP = "CAP"
    THRESHOLD = "THRESHOLD"
    SCORING = "SCORING"

class RuleSet(Base):
    __tablename__ = "rule_sets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brd_document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brd_documents.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[RuleSetStatus] = mapped_column(SAEnum(RuleSetStatus), default=RuleSetStatus.DRAFT)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    brd_document = relationship("BrdDocument", back_populates="rule_sets")
    rules = relationship("Rule", back_populates="rule_set", cascade="all, delete-orphan")
    simulations = relationship("Simulation", back_populates="rule_set")

class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_set_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rule_sets.id"))
    rule_id: Mapped[str] = mapped_column(String(32))
    rule_name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_type: Mapped[RuleType] = mapped_column(SAEnum(RuleType))
    conditions: Mapped[dict] = mapped_column(JSON)
    actions: Mapped[dict] = mapped_column(JSON)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    compiled_expression: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_section: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_conflicts: Mapped[bool] = mapped_column(Boolean, default=False)
    conflict_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    rule_set = relationship("RuleSet", back_populates="rules")
```

**Step 3: Create models/dataset.py**

```python
import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, Enum as SAEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class DatasetFileType(str, enum.Enum):
    CSV = "CSV"
    JSON = "JSON"

class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str] = mapped_column(String(1024))
    file_type: Mapped[DatasetFileType] = mapped_column(SAEnum(DatasetFileType))
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    column_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sample_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    data_profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    simulations = relationship("Simulation", back_populates="dataset")
```

**Step 4: Create models/simulation.py**

```python
import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, Enum as SAEnum, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class SimulationStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Simulation(Base):
    __tablename__ = "simulations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scenario_name: Mapped[str] = mapped_column(String(256))
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id"))
    rule_set_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rule_sets.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[SimulationStatus] = mapped_column(SAEnum(SimulationStatus), default=SimulationStatus.PENDING)
    parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    dataset = relationship("Dataset", back_populates="simulations")
    rule_set = relationship("RuleSet", back_populates="simulations")
    results = relationship("SimulationResult", back_populates="simulation", cascade="all, delete-orphan")

class SimulationResult(Base):
    __tablename__ = "simulation_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    simulation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("simulations.id"))
    summary_stats: Mapped[dict] = mapped_column(JSON)
    segment_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    customer_diffs_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    financial_impact: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    conflict_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    simulation = relationship("Simulation", back_populates="results")

class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    simulation_ids: Mapped[dict] = mapped_column(JSON, default=list)
    comparison_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

**Step 5: Create models/__init__.py**

```python
from app.models.brd import BrdDocument, FileType
from app.models.rule import RuleSet, Rule, RuleSetStatus, RuleType
from app.models.dataset import Dataset, DatasetFileType
from app.models.simulation import Simulation, SimulationResult, Scenario, SimulationStatus

__all__ = [
    "BrdDocument", "FileType",
    "RuleSet", "Rule", "RuleSetStatus", "RuleType",
    "Dataset", "DatasetFileType",
    "Simulation", "SimulationResult", "Scenario", "SimulationStatus",
]
```

**Step 6: Setup Alembic and create initial migration**

```bash
cd backend
alembic init alembic
# Edit alembic/env.py to import Base and models
# Edit alembic.ini to use DATABASE_URL
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

**Step 7: Commit**

```bash
git add backend/app/models/ backend/alembic/
git commit -m "feat: add database models for BRDs, rules, datasets, simulations"
```

---

### Task 1.3: Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/brd.py`
- Create: `backend/app/schemas/rule.py`
- Create: `backend/app/schemas/dataset.py`
- Create: `backend/app/schemas/simulation.py`
- Create: `backend/app/schemas/__init__.py`

**Step 1: Create schemas/rule.py** (core schema — others depend on this)

```python
from pydantic import BaseModel, Field
from typing import Any
from enum import Enum

class RuleTypeEnum(str, Enum):
    ELIGIBILITY = "ELIGIBILITY"
    PRICING = "PRICING"
    CAP = "CAP"
    THRESHOLD = "THRESHOLD"
    SCORING = "SCORING"

class Condition(BaseModel):
    field: str = Field(description="Data field name, e.g. 'bureau_score'")
    operator: str = Field(description="Comparison operator: >=, <=, ==, !=, in, not_in, between")
    value: Any = Field(description="Threshold value or list of values")
    logic: str = Field(default="AND", description="AND | OR for chaining with next condition")

class Action(BaseModel):
    action_type: str = Field(description="SET | REJECT | ADJUST | FLAG")
    target_field: str = Field(description="Field to modify, e.g. 'decision_status'")
    value: Any = Field(description="New value or delta")
    description: str = Field(description="Human-readable action description")

class RuleDefinition(BaseModel):
    rule_id: str
    rule_name: str
    description: str
    rule_type: RuleTypeEnum
    conditions: list[Condition]
    actions: list[Action]
    priority: int = 0
    source_section: str = ""
    confidence: float = 1.0

class RuleResponse(BaseModel):
    id: str
    rule_id: str
    rule_name: str
    description: str | None
    rule_type: str
    conditions: list[dict]
    actions: list[dict]
    priority: int
    confidence: float
    compiled_expression: str | None
    has_conflicts: bool
    conflict_details: dict | None

    class Config:
        from_attributes = True

class RuleSetResponse(BaseModel):
    id: str
    brd_document_id: str
    version: int
    name: str
    description: str | None
    status: str
    rules: list[RuleResponse] = []
    created_at: str

    class Config:
        from_attributes = True

class RuleUpdateRequest(BaseModel):
    rule_name: str | None = None
    description: str | None = None
    rule_type: RuleTypeEnum | None = None
    conditions: list[Condition] | None = None
    actions: list[Action] | None = None
    priority: int | None = None
```

**Step 2: Create schemas/brd.py**

```python
from pydantic import BaseModel

class BrdUploadResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    created_at: str
    rule_set_id: str | None = None

class BrdListResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    created_at: str
    rule_set_count: int = 0

    class Config:
        from_attributes = True
```

**Step 3: Create schemas/dataset.py**

```python
from pydantic import BaseModel

class DatasetUploadResponse(BaseModel):
    id: str
    name: str
    file_type: str
    row_count: int
    column_schema: dict | None
    sample_data: dict | None
    created_at: str

class DatasetListResponse(BaseModel):
    id: str
    name: str
    description: str | None
    file_type: str
    row_count: int
    created_at: str

    class Config:
        from_attributes = True

class DatasetProfileResponse(BaseModel):
    id: str
    name: str
    row_count: int
    column_schema: dict | None
    data_profile: dict | None
    sample_data: dict | None
```

**Step 4: Create schemas/simulation.py**

```python
from pydantic import BaseModel

class SimulationCreateRequest(BaseModel):
    scenario_name: str
    dataset_id: str
    rule_set_id: str
    parameters: dict | None = None

class SimulationResponse(BaseModel):
    id: str
    scenario_name: str
    dataset_id: str
    rule_set_id: str
    version: int
    status: str
    created_at: str
    completed_at: str | None

    class Config:
        from_attributes = True

class ImpactSummary(BaseModel):
    total_customers: int
    affected_customers: int
    affected_percentage: float
    decision_changes: dict
    amount_changes: dict
    segment_breakdown: dict
    financial_impact: dict

class SimulationResultResponse(BaseModel):
    id: str
    simulation_id: str
    summary_stats: dict
    segment_analysis: dict | None
    financial_impact: dict | None
    conflict_report: dict | None
    created_at: str

    class Config:
        from_attributes = True

class ScenarioCreateRequest(BaseModel):
    name: str
    description: str | None = None
    simulation_ids: list[str]

class ScenarioResponse(BaseModel):
    id: str
    name: str
    description: str | None
    simulation_ids: list[str]
    comparison_result: dict | None
    created_at: str

    class Config:
        from_attributes = True
```

**Step 5: Create schemas/__init__.py with all exports**

**Step 6: Commit**

```bash
git add backend/app/schemas/
git commit -m "feat: add Pydantic schemas for API request/response models"
```

---

## Phase 2: Sample Data & BRDs

### Task 2.1: Generate Sample Customer Dataset (CSV)

**Files:**
- Create: `backend/data/sample_datasets/loan_applications_500.csv`
- Create: `backend/scripts/generate_sample_data.py`

**Step 1: Create data generation script**

Write a Python script that generates 500 realistic loan application records with:
- `customer_id`: CUST-000001 to CUST-000500
- `age`: 22-60 (normal dist centered at 35)
- `employment_type`: SALARIED (70%), SELF_EMPLOYED (20%), PROFESSIONAL (10%)
- `employer_type`: PRIVATE (60%), GOVERNMENT (15%), MNC (25%) — for SALARIED only
- `monthly_income`: 25000-200000 (log-normal dist, median ~55000)
- `employment_tenure_months`: 6-240
- `residence_type`: RENTED (45%), OWNED (40%), COMPANY (15%)
- `city_tier`: TIER_1 (40%), TIER_2 (35%), TIER_3 (25%)
- `marital_status`: MARRIED (55%), SINGLE (35%), DIVORCED (10%)
- `dependents`: 0-4
- `bureau_score`: 550-850 (normal dist centered at 710, std 60)
- `active_loans`: 0-8
- `closed_loans`: 0-12
- `unsecured_loans`: 0-4
- `credit_utilization_ratio`: 0.05-0.95
- `max_dpd_last_12m`: 0 (80%), 1-30 (15%), 31-90 (5%)
- `inquiries_last_3m`: 0-6
- `oldest_trade_line_months`: 6-120
- `monthly_salary_credit`: close to monthly_income (within 5%)
- `salary_credit_consistency_6m`: 0.60-0.99
- `average_monthly_balance_6m`: 10000-500000
- `cheque_bounces_6m`: 0 (90%), 1-3 (10%)
- `emi_obligation_amount`: 0-40000
- `cash_deposits_6m`: 0-20
- `banking_stability_index`: 0.40-0.95
- `desired_amount`: 50000-500000
- `loan_type`: PERSONAL (100% for MVP)
- Calculated fields: `dti_ratio`, `net_disposable_income`, `g5_score`, `g6_score`
- Decision fields (baseline): `decision_status` (APPROVED/REJECTED/CONDITIONAL), `eligible_amount`, `interest_rate`

Baseline decision logic (the "current" rules):
- bureau_score >= 700 → eligible
- dti_ratio <= 0.40 → eligible
- monthly_income >= 25000 → eligible
- All three met → APPROVED, else REJECTED
- eligible_amount = min(desired_amount, annual_income * 0.35)
- interest_rate = base rate based on bureau score bands

**Step 2: Run script to generate CSV**

```bash
cd backend
python scripts/generate_sample_data.py
# Output: data/sample_datasets/loan_applications_500.csv (500 rows)
```

**Step 3: Commit**

```bash
git add backend/scripts/generate_sample_data.py backend/data/sample_datasets/
git commit -m "feat: add sample data generation script and 500-row loan application dataset"
```

---

### Task 2.2: Create Sample BRD Documents

**Files:**
- Create: `backend/data/sample_brds/BRD-001-DTI-Cap-Tightening.md` (will convert to PDF)
- Create: `backend/data/sample_brds/BRD-002-Income-Verification.md`
- Create: `backend/data/sample_brds/BRD-003-Pricing-Restructure.md`
- Create: `backend/data/sample_brds/BRD-004-Post-COVID-Tightening.md`
- Create: `backend/scripts/generate_sample_brds.py`

**Step 1: Create BRD-001 content**

Write a realistic BRD document for "DTI Cap Tightening" that includes:
- Document header (title, version, date, author, department)
- Executive Summary section
- Background & Rationale section
- Rule Changes section with:
  - Rule 1: Reduce maximum DTI ratio from 0.40 to 0.35 for unsecured personal loans
  - Rule 2: Increase minimum bureau score eligibility from 700 to 720
  - Rule 3: Reject applications with more than 3 credit inquiries in last 3 months
- Impact Assessment section (expected outcomes)
- Implementation Timeline section
- Approval section

Format it like a real corporate BRD with numbered sections, tables, and business language.

**Step 2: Create BRD-002, BRD-003, BRD-004** following the same template

BRD-002 (Income Verification Enhancement):
- Min monthly income 50,000 for loans > 150,000
- Salary consistency >= 0.85
- Banking stability index >= 0.75

BRD-003 (Pricing Tier Restructure):
- 5-tier pricing (was 3-tier) based on bureau score bands
- Bureau 750+ gets 50bps reduction
- >2 active unsecured loans get 100bps surcharge

BRD-004 (Post-COVID Risk Tightening — rejection scenario):
- Min bureau score 750
- DTI cap 0.30
- Min employment tenure 24 months
- Self-employed capped at 100,000
- Cash deposit ratio >20% triggers rejection

**Step 3: Create script to convert markdown BRDs to PDF**

Use reportlab or python-docx to create properly formatted PDF/DOCX files from the markdown content.

**Step 4: Generate the PDF/DOCX files**

```bash
cd backend
python scripts/generate_sample_brds.py
# Output: data/sample_brds/BRD-001.pdf, BRD-002.pdf, BRD-003.pdf, BRD-004.pdf
```

**Step 5: Commit**

```bash
git add backend/data/sample_brds/ backend/scripts/generate_sample_brds.py
git commit -m "feat: add 4 sample BRD documents for testing"
```

---

## Phase 3: Core Backend APIs

### Task 3.1: BRD Upload API

**Files:**
- Create: `backend/app/api/v1/brds.py`
- Create: `backend/app/services/brd_service.py`
- Create: `backend/tests/api/test_brds.py`

**Step 1: Write failing test**

```python
# tests/api/test_brds.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_upload_brd_pdf():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with open("data/sample_brds/BRD-001.pdf", "rb") as f:
            response = await client.post(
                "/api/v1/brds/upload",
                files={"file": ("BRD-001.pdf", f, "application/pdf")}
            )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "BRD-001.pdf"
    assert data["file_type"] == "PDF"
    assert "id" in data

@pytest.mark.asyncio
async def test_list_brds():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/brds")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/api/test_brds.py -v
# Expected: FAIL — routes don't exist yet
```

**Step 3: Implement brd_service.py**

```python
# app/services/brd_service.py
import uuid
import shutil
from pathlib import Path
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.brd import BrdDocument, FileType
from app.config import settings

async def upload_brd(file: UploadFile, db: AsyncSession) -> BrdDocument:
    file_ext = Path(file.filename).suffix.lower()
    file_type = FileType.PDF if file_ext == ".pdf" else FileType.DOCX

    file_id = str(uuid.uuid4())
    upload_dir = Path(settings.upload_dir) / "brds"
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{file_id}{file_ext}"

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    brd = BrdDocument(
        filename=file.filename,
        file_path=str(file_path),
        file_type=file_type,
    )
    db.add(brd)
    await db.commit()
    await db.refresh(brd)
    return brd

async def list_brds(db: AsyncSession) -> list[BrdDocument]:
    result = await db.execute(select(BrdDocument).order_by(BrdDocument.created_at.desc()))
    return list(result.scalars().all())

async def get_brd(brd_id: str, db: AsyncSession) -> BrdDocument | None:
    result = await db.execute(select(BrdDocument).where(BrdDocument.id == uuid.UUID(brd_id)))
    return result.scalar_one_or_none()
```

**Step 4: Implement api/v1/brds.py**

```python
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services import brd_service
from app.schemas.brd import BrdUploadResponse, BrdListResponse

router = APIRouter(prefix="/brds", tags=["BRDs"])

@router.post("/upload", response_model=BrdUploadResponse)
async def upload_brd(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    if not file.filename.endswith((".pdf", ".docx")):
        raise HTTPException(400, "Only PDF and DOCX files are supported")
    brd = await brd_service.upload_brd(file, db)
    return BrdUploadResponse(
        id=str(brd.id),
        filename=brd.filename,
        file_type=brd.file_type.value,
        created_at=brd.created_at.isoformat(),
    )

@router.get("", response_model=list[BrdListResponse])
async def list_brds(db: AsyncSession = Depends(get_db)):
    brds = await brd_service.list_brds(db)
    return [BrdListResponse(
        id=str(b.id), filename=b.filename, file_type=b.file_type.value,
        created_at=b.created_at.isoformat(),
    ) for b in brds]

@router.get("/{brd_id}")
async def get_brd(brd_id: str, db: AsyncSession = Depends(get_db)):
    brd = await brd_service.get_brd(brd_id, db)
    if not brd:
        raise HTTPException(404, "BRD not found")
    return brd
```

**Step 5: Register router in main.py**

```python
from app.api.v1.brds import router as brds_router
app.include_router(brds_router, prefix="/api/v1")
```

**Step 6: Run tests**

```bash
pytest tests/api/test_brds.py -v
# Expected: PASS
```

**Step 7: Commit**

```bash
git add backend/app/api/v1/brds.py backend/app/services/brd_service.py backend/tests/api/test_brds.py
git commit -m "feat: add BRD upload and listing API"
```

---

### Task 3.2: Dataset Upload API

**Files:**
- Create: `backend/app/api/v1/datasets.py`
- Create: `backend/app/services/dataset_service.py`
- Create: `backend/tests/api/test_datasets.py`

**Step 1: Write failing tests**

Tests for: upload CSV, upload JSON, list datasets, get dataset with profile.

**Step 2: Implement dataset_service.py**

Key logic:
- Accept CSV or JSON upload
- Use Pandas to read the file, detect schema (column names, types)
- Generate data profile (min, max, mean, nulls, distributions for numeric columns)
- Save sample_data (first 10 rows as JSON)
- Persist metadata to PostgreSQL

```python
async def upload_dataset(file: UploadFile, name: str, db: AsyncSession) -> Dataset:
    # Save file
    # Read with pandas
    df = pd.read_csv(file_path) if file_type == "CSV" else pd.read_json(file_path)
    # Generate schema
    column_schema = {col: str(df[col].dtype) for col in df.columns}
    # Generate profile
    data_profile = {}
    for col in df.select_dtypes(include='number').columns:
        data_profile[col] = {
            "min": float(df[col].min()),
            "max": float(df[col].max()),
            "mean": float(df[col].mean()),
            "median": float(df[col].median()),
            "std": float(df[col].std()),
            "nulls": int(df[col].isnull().sum()),
        }
    # Save to DB
    ...
```

**Step 3: Implement api/v1/datasets.py**

Endpoints: `POST /upload`, `GET /`, `GET /{id}`, `GET /{id}/profile`, `DELETE /{id}`

**Step 4: Run tests, verify pass**

**Step 5: Commit**

```bash
git commit -m "feat: add dataset upload API with auto-profiling"
```

---

### Task 3.3: Simulation & Results APIs

**Files:**
- Create: `backend/app/api/v1/simulations.py`
- Create: `backend/app/services/simulation_service.py`
- Create: `backend/app/api/v1/scenarios.py`
- Create: `backend/app/services/scenario_service.py`
- Create: `backend/tests/api/test_simulations.py`

**Step 1: Write failing tests**

Tests for: create simulation, get simulation status, get results, create scenario, compare scenarios.

**Step 2: Implement simulation_service.py**

For now, simulation creation just creates the DB record with PENDING status. Actual simulation execution comes in Phase 4.

```python
async def create_simulation(request: SimulationCreateRequest, db: AsyncSession) -> Simulation:
    sim = Simulation(
        scenario_name=request.scenario_name,
        dataset_id=uuid.UUID(request.dataset_id),
        rule_set_id=uuid.UUID(request.rule_set_id),
    )
    db.add(sim)
    await db.commit()
    await db.refresh(sim)
    return sim
```

**Step 3: Implement API routes**

Endpoints:
- `POST /simulations` — create and queue simulation
- `GET /simulations` — list simulations
- `GET /simulations/{id}` — get simulation with status
- `GET /simulations/{id}/results` — get results
- `POST /scenarios` — create scenario from simulation IDs
- `GET /scenarios/{id}` — get scenario with comparison

**Step 4: Run tests, commit**

```bash
git commit -m "feat: add simulation and scenario CRUD APIs"
```

---

### Task 3.4: Rule Set CRUD APIs

**Files:**
- Create: `backend/app/api/v1/rules.py`
- Create: `backend/app/services/rule_service.py`
- Create: `backend/tests/api/test_rules.py`

**Step 1: Write failing tests**

Tests for: list rule sets, get rule set with rules, update individual rule, approve rule set, version rule set.

**Step 2: Implement rule_service.py**

Key operations:
- Get rule set by ID (with rules eager-loaded)
- Update rule (edit conditions/actions)
- Approve rule set (status → APPROVED)
- Version rule set (clone current version, increment version number)
- Delete rule from rule set

**Step 3: Implement api/v1/rules.py**

Endpoints:
- `GET /rule-sets` — list all rule sets
- `GET /rule-sets/{id}` — get rule set with rules
- `PATCH /rule-sets/{id}/approve` — approve rule set
- `POST /rule-sets/{id}/version` — create new version
- `PATCH /rules/{id}` — update individual rule
- `DELETE /rules/{id}` — delete rule
- `POST /rule-sets/{id}/rules` — add rule manually

**Step 4: Run tests, commit**

```bash
git commit -m "feat: add rule set CRUD with versioning and approval"
```

---

## Phase 4: LangGraph Pipeline

### Task 4.1: Document Parser Node

**Files:**
- Create: `backend/app/pipeline/document_parser.py`
- Create: `backend/app/pipeline/schemas.py`
- Create: `backend/tests/pipeline/test_document_parser.py`

**Step 1: Write failing test**

```python
# tests/pipeline/test_document_parser.py
import pytest
from app.pipeline.document_parser import parse_document
from app.pipeline.schemas import DocumentSection

def test_parse_pdf_brd():
    with open("data/sample_brds/BRD-001.pdf", "rb") as f:
        content = f.read()
    sections = parse_document(content, "BRD-001.pdf")
    assert len(sections) > 0
    assert all(isinstance(s, DocumentSection) for s in sections)
    # Should find rule-related sections
    rule_sections = [s for s in sections if s.section_type == "RULES"]
    assert len(rule_sections) > 0
```

**Step 2: Run test to verify it fails**

**Step 3: Implement pipeline/schemas.py**

```python
from pydantic import BaseModel
from typing import Any
from enum import Enum

class SectionType(str, Enum):
    HEADER = "HEADER"
    BACKGROUND = "BACKGROUND"
    RULES = "RULES"
    IMPACT = "IMPACT"
    TIMELINE = "TIMELINE"
    OTHER = "OTHER"

class DocumentSection(BaseModel):
    section_id: str
    title: str
    content: str
    section_type: SectionType
    page_number: int | None = None
```

**Step 4: Implement document_parser.py**

```python
from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from app.pipeline.schemas import DocumentSection, SectionType

def parse_document(content: bytes, filename: str) -> list[DocumentSection]:
    ext = Path(filename).suffix.lower()
    # Write to temp file, use appropriate loader
    # Split by section headers (numbered sections, bold headers)
    # Classify each section by type using keyword matching
    # Return structured sections
    ...
```

Uses LangChain document loaders for PDF/DOCX extraction, then applies section detection heuristics (regex for numbered headers like "2.1", "3.0", etc.) and keyword-based classification (words like "rule", "criteria", "threshold" → RULES section).

**Step 5: Run test, verify pass**

**Step 6: Commit**

```bash
git commit -m "feat: add document parser node for BRD section extraction"
```

---

### Task 4.2: Rule Extractor Node

**Files:**
- Create: `backend/app/pipeline/rule_extractor.py`
- Create: `backend/tests/pipeline/test_rule_extractor.py`

**Step 1: Write failing test**

```python
def test_extract_rules_from_dti_brd():
    sections = [DocumentSection(
        section_id="s1",
        title="Rule Changes",
        content="Rule 1: The maximum DTI ratio for unsecured personal loans shall be reduced from 0.40 to 0.35...",
        section_type=SectionType.RULES,
    )]
    rules = extract_rules(sections)
    assert len(rules) >= 1
    assert rules[0].rule_type == RuleTypeEnum.THRESHOLD
    assert any(c.field == "dti_ratio" for c in rules[0].conditions)
```

**Step 2: Implement rule_extractor.py**

```python
from anthropic import Anthropic
from app.pipeline.schemas import DocumentSection
from app.schemas.rule import RuleDefinition, Condition, Action, RuleTypeEnum

EXTRACTION_PROMPT = """You are a business rule extraction specialist. Given sections from a Business Requirement Document (BRD), extract each business rule into a structured format.

For each rule found, provide:
- rule_id: Sequential ID like RULE-001, RULE-002
- rule_name: Short descriptive name
- description: Full description of the rule
- rule_type: One of ELIGIBILITY, PRICING, CAP, THRESHOLD, SCORING
- conditions: List of conditions (field, operator, value)
- actions: List of actions (action_type, target_field, value, description)
- priority: Execution order (lower = first)
- confidence: Your confidence in the extraction (0.0 to 1.0)

Available fields in customer data: bureau_score, dti_ratio, monthly_income, employment_type,
employment_tenure_months, active_loans, unsecured_loans, credit_utilization_ratio,
inquiries_last_3m, salary_credit_consistency_6m, banking_stability_index, desired_amount,
cash_deposits_6m, city_tier, max_dpd_last_12m, cheque_bounces_6m

Available operators: >=, <=, >, <, ==, !=, in, not_in, between

Available action_types: SET, REJECT, ADJUST, FLAG

Respond with a JSON array of rule objects."""

def extract_rules(sections: list[DocumentSection]) -> list[RuleDefinition]:
    client = Anthropic()
    rule_sections = [s for s in sections if s.section_type == SectionType.RULES]
    combined_text = "\n\n".join(f"### {s.title}\n{s.content}" for s in rule_sections)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": f"{EXTRACTION_PROMPT}\n\n---\n\nBRD Content:\n{combined_text}"}],
    )
    # Parse JSON response into RuleDefinition objects
    ...
```

**Step 3: Run test, verify pass**

**Step 4: Commit**

```bash
git commit -m "feat: add LLM-powered rule extractor using Claude"
```

---

### Task 4.3: Rule Validator & Conflict Detector

**Files:**
- Create: `backend/app/pipeline/rule_validator.py`
- Create: `backend/tests/pipeline/test_rule_validator.py`

**Step 1: Write failing test**

```python
def test_detect_conflicting_rules():
    rules = [
        RuleDefinition(
            rule_id="RULE-001", rule_name="Approve high score",
            rule_type=RuleTypeEnum.ELIGIBILITY,
            conditions=[Condition(field="bureau_score", operator=">=", value=720)],
            actions=[Action(action_type="SET", target_field="decision", value="APPROVED", description="Approve")],
            ...
        ),
        RuleDefinition(
            rule_id="RULE-002", rule_name="Reject low tenure",
            rule_type=RuleTypeEnum.ELIGIBILITY,
            conditions=[Condition(field="employment_tenure_months", operator="<", value=24)],
            actions=[Action(action_type="REJECT", target_field="decision", value="REJECTED", description="Reject")],
            ...
        ),
    ]
    result = validate_rules(rules)
    # These rules can overlap (high score + low tenure customer) — should flag potential conflict
    assert len(result.potential_conflicts) > 0
```

**Step 2: Implement rule_validator.py**

```python
from app.schemas.rule import RuleDefinition
from app.pipeline.schemas import ValidationResult, RuleConflict

def validate_rules(rules: list[RuleDefinition]) -> ValidationResult:
    warnings = []
    conflicts = []

    # Check completeness
    for rule in rules:
        if not rule.conditions:
            warnings.append(f"{rule.rule_id}: No conditions defined")
        if not rule.actions:
            warnings.append(f"{rule.rule_id}: No actions defined")
        if rule.confidence < 0.7:
            warnings.append(f"{rule.rule_id}: Low extraction confidence ({rule.confidence})")

    # Check for conflicts — rules that target the same field with contradictory actions
    # AND have conditions that could overlap
    for i, r1 in enumerate(rules):
        for r2 in rules[i+1:]:
            if _actions_conflict(r1.actions, r2.actions):
                if _conditions_could_overlap(r1.conditions, r2.conditions):
                    conflicts.append(RuleConflict(
                        rule_id_1=r1.rule_id,
                        rule_id_2=r2.rule_id,
                        conflict_type="CONTRADICTORY_ACTIONS",
                        description=f"Rules target same field with different outcomes",
                    ))

    return ValidationResult(
        is_valid=len(conflicts) == 0,
        warnings=warnings,
        potential_conflicts=conflicts,
    )
```

**Step 3: Run test, verify pass, commit**

```bash
git commit -m "feat: add rule validator with conflict detection"
```

---

### Task 4.4: Rule Compiler

**Files:**
- Create: `backend/app/pipeline/rule_compiler.py`
- Create: `backend/tests/pipeline/test_rule_compiler.py`

**Step 1: Write failing test**

```python
def test_compile_threshold_rule():
    rule = RuleDefinition(
        rule_id="RULE-001",
        rule_name="DTI Cap",
        rule_type=RuleTypeEnum.THRESHOLD,
        conditions=[Condition(field="dti_ratio", operator=">", value=0.35)],
        actions=[Action(action_type="REJECT", target_field="decision_status", value="REJECTED", description="DTI too high")],
        ...
    )
    compiled = compile_rule(rule)
    assert compiled.condition_expr is not None
    # Test against a sample DataFrame
    df = pd.DataFrame({"dti_ratio": [0.30, 0.36, 0.40]})
    mask = compiled.evaluate(df)
    assert mask.tolist() == [False, True, True]
```

**Step 2: Implement rule_compiler.py**

```python
import pandas as pd
from app.schemas.rule import RuleDefinition, Condition, Action

class CompiledRule:
    def __init__(self, rule_def: RuleDefinition, condition_expr: str, actions: list[Action]):
        self.rule_def = rule_def
        self.condition_expr = condition_expr
        self.actions = actions
        self.priority = rule_def.priority

    def evaluate(self, df: pd.DataFrame) -> pd.Series:
        """Returns boolean mask of rows matching conditions."""
        return df.eval(self.condition_expr)

    def apply(self, df: pd.DataFrame, mask: pd.Series) -> pd.DataFrame:
        """Apply actions to matching rows."""
        result = df.copy()
        for action in self.actions:
            if action.action_type == "SET":
                result.loc[mask, action.target_field] = action.value
            elif action.action_type == "REJECT":
                result.loc[mask, action.target_field] = "REJECTED"
            elif action.action_type == "ADJUST":
                result.loc[mask, action.target_field] += action.value
            elif action.action_type == "FLAG":
                result.loc[mask, f"flag_{action.target_field}"] = True
        return result

def compile_rule(rule: RuleDefinition) -> CompiledRule:
    """Convert RuleDefinition conditions to a Pandas eval expression."""
    expr_parts = []
    for i, cond in enumerate(rule.conditions):
        part = _condition_to_expr(cond)
        if i > 0:
            logic = rule.conditions[i-1].logic
            expr_parts.append(f" {'&' if logic == 'AND' else '|'} ")
        expr_parts.append(part)
    condition_expr = "".join(expr_parts)
    return CompiledRule(rule, condition_expr, rule.actions)

def _condition_to_expr(cond: Condition) -> str:
    op_map = {">=": ">=", "<=": "<=", ">": ">", "<": "<", "==": "==", "!=": "!="}
    if cond.operator in op_map:
        return f"(`{cond.field}` {op_map[cond.operator]} {cond.value})"
    elif cond.operator == "in":
        return f"(`{cond.field}`.isin({cond.value}))"
    elif cond.operator == "between":
        return f"(`{cond.field}` >= {cond.value[0]} & `{cond.field}` <= {cond.value[1]})"
    raise ValueError(f"Unknown operator: {cond.operator}")
```

**Step 3: Run tests, verify pass, commit**

```bash
git commit -m "feat: add rule compiler converting rules to Pandas expressions"
```

---

### Task 4.5: Simulation Engine

**Files:**
- Create: `backend/app/simulation/engine.py`
- Create: `backend/app/simulation/baseline.py`
- Create: `backend/app/simulation/comparator.py`
- Create: `backend/tests/simulation/test_engine.py`

**Step 1: Write failing test**

```python
def test_simulation_detects_dti_rejections():
    # Load sample data
    df = pd.read_csv("data/sample_datasets/loan_applications_500.csv")

    # Define a rule: reject if DTI > 0.35 (stricter than current 0.40)
    rules = [CompiledRule(...)]  # DTI threshold rule

    result = run_simulation(df, rules, baseline_rules=get_default_baseline_rules())

    assert result.total_customers == 500
    assert result.affected_customers > 0
    assert result.decision_changes["approved_to_rejected"] > 0
    # Customers with DTI between 0.35 and 0.40 should flip to rejected
```

**Step 2: Implement simulation/baseline.py**

```python
import pandas as pd

DEFAULT_BASELINE_RULES = {
    "min_bureau_score": 700,
    "max_dti_ratio": 0.40,
    "min_monthly_income": 25000,
}

def apply_baseline(df: pd.DataFrame) -> pd.DataFrame:
    """Apply current/default rules to establish baseline decisions."""
    result = df.copy()
    result["baseline_decision"] = "APPROVED"

    # Apply current rules
    result.loc[result["bureau_score"] < DEFAULT_BASELINE_RULES["min_bureau_score"], "baseline_decision"] = "REJECTED"
    result.loc[result["dti_ratio"] > DEFAULT_BASELINE_RULES["max_dti_ratio"], "baseline_decision"] = "REJECTED"
    result.loc[result["monthly_income"] < DEFAULT_BASELINE_RULES["min_monthly_income"], "baseline_decision"] = "REJECTED"

    # Calculate baseline amounts and rates
    result["baseline_eligible_amount"] = result.apply(_calc_eligible_amount, axis=1)
    result["baseline_interest_rate"] = result["bureau_score"].apply(_calc_interest_rate)

    return result
```

**Step 3: Implement simulation/engine.py**

```python
import pandas as pd
from app.pipeline.rule_compiler import CompiledRule
from app.simulation.baseline import apply_baseline
from app.simulation.comparator import compare_results

class SimulationResult:
    total_customers: int
    affected_customers: int
    decision_changes: dict
    amount_changes: dict
    baseline_df: pd.DataFrame
    simulated_df: pd.DataFrame
    diff_df: pd.DataFrame

def run_simulation(
    df: pd.DataFrame,
    new_rules: list[CompiledRule],
    baseline_rules: dict | None = None,
) -> SimulationResult:
    # Phase 1: Baseline
    baseline_df = apply_baseline(df)

    # Phase 2: Apply new rules
    simulated_df = baseline_df.copy()
    simulated_df["sim_decision"] = simulated_df["baseline_decision"]
    simulated_df["sim_eligible_amount"] = simulated_df["baseline_eligible_amount"]
    simulated_df["sim_interest_rate"] = simulated_df["baseline_interest_rate"]

    conflict_log = []
    for rule in sorted(new_rules, key=lambda r: r.priority):
        mask = rule.evaluate(simulated_df)
        prev_decisions = simulated_df.loc[mask, "sim_decision"].copy()
        simulated_df = rule.apply(simulated_df, mask)
        # Check for conflicts
        new_decisions = simulated_df.loc[mask, "sim_decision"]
        flipped = prev_decisions != new_decisions
        if flipped.any():
            conflict_log.append({
                "rule_id": rule.rule_def.rule_id,
                "affected_count": int(flipped.sum()),
            })

    # Phase 3: Compare
    return compare_results(baseline_df, simulated_df, conflict_log)
```

**Step 4: Implement simulation/comparator.py**

```python
def compare_results(baseline_df, simulated_df, conflict_log) -> SimulationResult:
    total = len(baseline_df)
    decision_col_b = "baseline_decision"
    decision_col_s = "sim_decision"

    approved_to_rejected = ((baseline_df[decision_col_b] == "APPROVED") & (simulated_df[decision_col_s] == "REJECTED")).sum()
    rejected_to_approved = ((baseline_df[decision_col_b] == "REJECTED") & (simulated_df[decision_col_s] == "APPROVED")).sum()

    amount_delta = simulated_df["sim_eligible_amount"] - baseline_df["baseline_eligible_amount"]
    affected = (baseline_df[decision_col_b] != simulated_df[decision_col_s]) | (amount_delta.abs() > 0)

    # Segment breakdown
    segments = {}
    for segment_col in ["bureau_score_band", "income_bracket", "city_tier"]:
        if segment_col in baseline_df.columns or segment_col == "bureau_score_band":
            # Create bands if needed
            ...

    return SimulationResult(
        total_customers=total,
        affected_customers=int(affected.sum()),
        decision_changes={
            "approved_to_rejected": int(approved_to_rejected),
            "rejected_to_approved": int(rejected_to_approved),
        },
        amount_changes={
            "increased": int((amount_delta > 0).sum()),
            "decreased": int((amount_delta < 0).sum()),
            "avg_delta": float(amount_delta.mean()),
        },
        segment_breakdown=segments,
        financial_impact={
            "total_exposure_change": float(amount_delta.sum()),
            "avg_loan_amount_change": float(amount_delta.mean()),
        },
        baseline_df=baseline_df,
        simulated_df=simulated_df,
        conflict_log=conflict_log,
    )
```

**Step 5: Run tests, verify pass, commit**

```bash
git commit -m "feat: add simulation engine with baseline, execution, and comparison"
```

---

### Task 4.6: Assemble LangGraph Pipeline

**Files:**
- Create: `backend/app/pipeline/graph.py`
- Create: `backend/tests/pipeline/test_graph.py`

**Step 1: Write failing test**

```python
def test_full_pipeline_with_sample_brd():
    with open("data/sample_brds/BRD-001.pdf", "rb") as f:
        brd_content = f.read()
    dataset_df = pd.read_csv("data/sample_datasets/loan_applications_500.csv")

    # Run pipeline (auto-approve for testing)
    result = run_pipeline(
        brd_content=brd_content,
        brd_filename="BRD-001.pdf",
        dataset_df=dataset_df,
        auto_approve=True,
    )

    assert result["impact_analysis"] is not None
    assert result["impact_analysis"].total_customers == 500
    assert result["impact_analysis"].affected_customers > 0
```

**Step 2: Implement pipeline/graph.py**

```python
from langgraph.graph import StateGraph, END
from app.pipeline.schemas import PipelineState
from app.pipeline.document_parser import parse_document
from app.pipeline.rule_extractor import extract_rules
from app.pipeline.rule_validator import validate_rules
from app.pipeline.rule_compiler import compile_rule
from app.simulation.engine import run_simulation

def build_pipeline() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("parse_document", parse_document_node)
    graph.add_node("extract_rules", extract_rules_node)
    graph.add_node("validate_rules", validate_rules_node)
    graph.add_node("compile_rules", compile_rules_node)
    graph.add_node("run_simulation", simulation_node)
    graph.add_node("analyze_impact", impact_node)

    graph.set_entry_point("parse_document")
    graph.add_edge("parse_document", "extract_rules")
    graph.add_edge("extract_rules", "validate_rules")
    graph.add_conditional_edges(
        "validate_rules",
        should_auto_approve,
        {"auto_approve": "compile_rules", "human_review": END}  # END = interrupt for human review
    )
    graph.add_edge("compile_rules", "run_simulation")
    graph.add_edge("run_simulation", "analyze_impact")
    graph.add_edge("analyze_impact", END)

    return graph.compile()

def parse_document_node(state: PipelineState) -> dict:
    sections = parse_document(state["brd_document"], state["brd_filename"])
    return {"parsed_sections": sections}

def extract_rules_node(state: PipelineState) -> dict:
    rules = extract_rules(state["parsed_sections"])
    return {"extracted_rules": rules}

def validate_rules_node(state: PipelineState) -> dict:
    result = validate_rules(state["extracted_rules"])
    return {"validation_result": result}

def should_auto_approve(state: PipelineState) -> str:
    if state.get("auto_approve"):
        return "auto_approve"
    return "human_review"

def compile_rules_node(state: PipelineState) -> dict:
    compiled = [compile_rule(r) for r in state["extracted_rules"]]
    return {"compiled_rules": compiled}

def simulation_node(state: PipelineState) -> dict:
    result = run_simulation(state["dataset_df"], state["compiled_rules"])
    return {"simulation_result": result}

def impact_node(state: PipelineState) -> dict:
    # Already computed in simulation — extract analysis
    return {"impact_analysis": state["simulation_result"]}

def run_pipeline(brd_content: bytes, brd_filename: str, dataset_df, auto_approve: bool = False):
    pipeline = build_pipeline()
    initial_state = {
        "brd_document": brd_content,
        "brd_filename": brd_filename,
        "dataset_df": dataset_df,
        "auto_approve": auto_approve,
    }
    return pipeline.invoke(initial_state)
```

**Step 3: Run test, verify pass, commit**

```bash
git commit -m "feat: assemble LangGraph pipeline connecting all nodes"
```

---

### Task 4.7: Pipeline API Integration

**Files:**
- Create: `backend/app/api/v1/pipeline.py`
- Modify: `backend/app/services/simulation_service.py`
- Create: `backend/tests/api/test_pipeline.py`

**Step 1: Write failing test**

```python
async def test_trigger_pipeline():
    # Upload a BRD and dataset first
    # Then trigger pipeline
    response = await client.post("/api/v1/pipeline/run", json={
        "brd_id": brd_id,
        "dataset_id": dataset_id,
        "scenario_name": "Test Scenario",
        "auto_approve": True,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["COMPLETED", "AWAITING_REVIEW"]
```

**Step 2: Implement api/v1/pipeline.py**

Endpoints:
- `POST /pipeline/run` — trigger full pipeline (sync for MVP, async via Celery later)
- `GET /pipeline/{run_id}/status` — get pipeline status
- `POST /pipeline/{run_id}/approve` — approve rules and continue pipeline
- `POST /pipeline/{run_id}/edit-rules` — edit rules and re-validate

**Step 3: Run test, verify pass, commit**

```bash
git commit -m "feat: add pipeline API for triggering and managing BRD processing"
```

---

## Phase 5: Frontend

### Task 5.1: Frontend Project Setup

**Files:**
- Create: `frontend/` — Next.js 14 project

**Step 1: Scaffold Next.js project**

```bash
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir
cd frontend
npm install recharts @tremor/react lucide-react axios
npx shadcn@latest init
npx shadcn@latest add button card input table tabs dialog badge separator
npx shadcn@latest add dropdown-menu select slider toast sheet
```

**Step 2: Create API client**

```typescript
// src/lib/api.ts
import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1",
});

export default api;
```

**Step 3: Create layout with sidebar navigation**

```typescript
// src/app/layout.tsx — main layout with sidebar
// Links: Dashboard, BRDs, Datasets, Simulations, Scenarios
```

**Step 4: Commit**

```bash
git commit -m "feat: scaffold Next.js frontend with shadcn/ui and navigation"
```

---

### Task 5.2: Dashboard Page

**Files:**
- Create: `frontend/src/app/page.tsx`
- Create: `frontend/src/components/dashboard/stats-cards.tsx`
- Create: `frontend/src/components/dashboard/recent-simulations.tsx`

**Step 1: Implement dashboard with:**
- 4 stat cards: Total BRDs, Total Simulations, Avg Impact Rate, Active Scenarios
- Recent simulations table with status badges
- Quick action buttons: Upload BRD, Upload Dataset

**Step 2: Connect to backend APIs**

**Step 3: Commit**

```bash
git commit -m "feat: add dashboard page with stats and recent simulations"
```

---

### Task 5.3: BRD Upload Page

**Files:**
- Create: `frontend/src/app/brds/page.tsx`
- Create: `frontend/src/app/brds/[id]/page.tsx`
- Create: `frontend/src/components/brds/upload-dropzone.tsx`
- Create: `frontend/src/components/brds/processing-status.tsx`

**Step 1: Implement BRD list page with upload dropzone**

Drag-and-drop area accepting PDF/DOCX. Shows list of previously uploaded BRDs.

**Step 2: Implement BRD detail page**

Shows parsed content, extracted rules preview, link to rule editor.

**Step 3: Add processing status component**

Stepper showing: Upload → Parsing → Extracting Rules → Validating → Ready for Review

**Step 4: Commit**

```bash
git commit -m "feat: add BRD upload page with drag-and-drop and processing status"
```

---

### Task 5.4: Rule Review & Editor Page

**Files:**
- Create: `frontend/src/app/rules/[ruleSetId]/page.tsx`
- Create: `frontend/src/components/rules/rule-table.tsx`
- Create: `frontend/src/components/rules/rule-editor-dialog.tsx`
- Create: `frontend/src/components/rules/conflict-panel.tsx`
- Create: `frontend/src/components/rules/version-sidebar.tsx`

**Step 1: Implement rule table**

Expandable rows showing:
- Rule name, type, confidence badge
- Conditions in human-readable form (e.g., "bureau_score >= 720")
- Actions in human-readable form (e.g., "REJECT application")
- Conflict indicator (red dot if has_conflicts)

**Step 2: Implement rule editor dialog**

Modal for editing:
- Rule name, description
- Add/remove conditions (field dropdown, operator dropdown, value input)
- Add/remove actions
- Priority adjustment

**Step 3: Implement conflict panel**

Side panel showing detected conflicts between rules with:
- Which rules conflict
- Why they conflict
- How many customers would be affected

**Step 4: Implement version sidebar**

Shows version history of the rule set with ability to compare versions.

**Step 5: Add approve/reject buttons**

Approve all rules → sets rule set status to APPROVED, enables simulation.

**Step 6: Commit**

```bash
git commit -m "feat: add rule review editor with conflict detection and versioning"
```

---

### Task 5.5: Dataset Manager Page

**Files:**
- Create: `frontend/src/app/datasets/page.tsx`
- Create: `frontend/src/app/datasets/[id]/page.tsx`
- Create: `frontend/src/components/datasets/upload-form.tsx`
- Create: `frontend/src/components/datasets/data-profile.tsx`
- Create: `frontend/src/components/datasets/sample-table.tsx`

**Step 1: Implement dataset list with upload form**

Upload form with name, description, file input (CSV/JSON).

**Step 2: Implement dataset detail page**

Shows:
- Column schema table (name, type, non-null count)
- Data profile charts (histograms for numeric columns using Recharts)
- Sample data table (first 20 rows)

**Step 3: Commit**

```bash
git commit -m "feat: add dataset manager with upload and data profiling"
```

---

### Task 5.6: Simulation Runner Page

**Files:**
- Create: `frontend/src/app/simulations/page.tsx`
- Create: `frontend/src/app/simulations/new/page.tsx`
- Create: `frontend/src/components/simulations/simulation-form.tsx`
- Create: `frontend/src/components/simulations/sensitivity-sliders.tsx`

**Step 1: Implement simulation list page**

Table of simulations with: scenario name, dataset, rule set, status, date.

**Step 2: Implement new simulation form**

- Select rule set (dropdown from approved rule sets)
- Select dataset (dropdown)
- Scenario name input
- Sensitivity sliders — for each numeric threshold in the selected rule set, show a slider with the BRD value as default and +-50% range

**Step 3: Implement run + progress tracking**

Submit triggers the pipeline API. Poll for status updates. Show progress bar.

**Step 4: Commit**

```bash
git commit -m "feat: add simulation runner with sensitivity sliders"
```

---

### Task 5.7: Impact Dashboard Page

**Files:**
- Create: `frontend/src/app/simulations/[id]/results/page.tsx`
- Create: `frontend/src/components/impact/summary-cards.tsx`
- Create: `frontend/src/components/impact/decision-sankey.tsx`
- Create: `frontend/src/components/impact/distribution-charts.tsx`
- Create: `frontend/src/components/impact/segment-table.tsx`
- Create: `frontend/src/components/impact/financial-panel.tsx`
- Create: `frontend/src/components/impact/customer-diff-table.tsx`

**Step 1: Implement summary cards**

4 cards: Affected Customers (count + %), Decision Flips, Amount Changes, Financial Impact.

**Step 2: Implement distribution charts**

Before/after overlaid histograms using Recharts for:
- Bureau score distribution
- DTI ratio distribution
- Loan amount distribution

**Step 3: Implement decision Sankey**

Sankey diagram showing flow: Approved→Approved, Approved→Rejected, Rejected→Approved, Rejected→Rejected. Use Recharts Sankey component.

**Step 4: Implement segment breakdown table**

Table with segments as rows (e.g., "Bureau 700-750", "Income 50K-75K") and metrics as columns (total, affected, % affected, avg amount change).

**Step 5: Implement financial impact panel**

Cards showing: Total Exposure Change, Revenue Impact, Expected Loss Change.

**Step 6: Implement customer diff table**

Searchable, sortable table showing per-customer changes:
- Customer ID, bureau score, DTI, income
- Before decision → After decision (with colored arrow)
- Before amount → After amount (with delta)
- Rules that triggered the change

**Step 7: Commit**

```bash
git commit -m "feat: add impact dashboard with charts, Sankey, and customer diff table"
```

---

### Task 5.8: Scenario Comparison Page

**Files:**
- Create: `frontend/src/app/scenarios/page.tsx`
- Create: `frontend/src/app/scenarios/[id]/page.tsx`
- Create: `frontend/src/app/scenarios/compare/page.tsx`
- Create: `frontend/src/components/scenarios/comparison-charts.tsx`
- Create: `frontend/src/components/scenarios/delta-table.tsx`

**Step 1: Implement scenario list and creation**

List of scenarios. Create scenario by selecting 2-3 simulations.

**Step 2: Implement comparison view**

Side-by-side:
- Bar chart comparing affected % across scenarios
- Overlay line chart of bureau score distributions
- Delta table: metric | Scenario A | Scenario B | Scenario C | Winner

**Step 3: Commit**

```bash
git commit -m "feat: add scenario comparison with side-by-side charts"
```

---

## Phase 6: Export & Polish

### Task 6.1: CSV Export

**Files:**
- Create: `backend/app/api/v1/export.py`
- Create: `backend/app/services/export_service.py`

**Step 1: Implement CSV export endpoint**

`GET /api/v1/export/simulation/{id}/csv` — returns the customer diff DataFrame as a downloadable CSV.

`GET /api/v1/export/simulation/{id}/summary-csv` — returns summary stats as CSV.

**Step 2: Add export buttons to frontend**

Add "Export CSV" buttons on the Impact Dashboard and Scenario Comparison pages.

**Step 3: Commit**

```bash
git commit -m "feat: add CSV export for simulation results"
```

---

### Task 6.2: PDF Report Generation

**Files:**
- Create: `backend/app/services/pdf_report.py`
- Modify: `backend/app/api/v1/export.py`

**Step 1: Implement PDF report using ReportLab**

`GET /api/v1/export/simulation/{id}/pdf` — generates a PDF with:
- Header: simulation name, date, BRD reference
- Executive summary (key metrics)
- Decision changes table
- Segment breakdown table
- Financial impact section
- Page numbers, footer

**Step 2: Add "Download Report" button to frontend**

**Step 3: Commit**

```bash
git commit -m "feat: add PDF report generation for simulation results"
```

---

### Task 6.3: Dashboard Stats API

**Files:**
- Create: `backend/app/api/v1/dashboard.py`
- Create: `backend/app/services/dashboard_service.py`

**Step 1: Implement dashboard aggregation endpoint**

`GET /api/v1/dashboard` — returns:
```json
{
  "total_brds": 4,
  "total_simulations": 12,
  "total_datasets": 3,
  "avg_impact_rate": 0.23,
  "recent_simulations": [...],
  "recent_scenarios": [...]
}
```

**Step 2: Connect dashboard page to this API**

**Step 3: Commit**

```bash
git commit -m "feat: add dashboard stats API and connect frontend"
```

---

### Task 6.4: Celery Async Simulation

**Files:**
- Create: `backend/app/tasks/simulation_task.py`
- Create: `backend/app/celery_app.py`
- Modify: `backend/app/api/v1/pipeline.py`

**Step 1: Setup Celery**

```python
# app/celery_app.py
from celery import Celery
from app.config import settings

celery_app = Celery("policy_impact_engine", broker=settings.redis_url)
```

**Step 2: Create simulation task**

```python
# app/tasks/simulation_task.py
@celery_app.task
def run_simulation_task(simulation_id: str):
    # Load simulation config from DB
    # Load dataset
    # Load compiled rules
    # Run simulation engine
    # Save results to DB
    # Update simulation status to COMPLETED
```

**Step 3: Update pipeline API to queue via Celery**

Instead of running synchronously, queue the simulation and return immediately with PENDING status. Frontend polls for completion.

**Step 4: Commit**

```bash
git commit -m "feat: add Celery async simulation execution"
```

---

## Phase 7: End-to-End Testing & Demo

### Task 7.1: End-to-End Integration Test

**Files:**
- Create: `backend/tests/test_e2e_pipeline.py`

**Step 1: Write E2E test**

```python
async def test_full_workflow():
    # 1. Upload BRD-001.pdf
    # 2. Upload loan_applications_500.csv
    # 3. Trigger pipeline with auto_approve=True
    # 4. Verify simulation completes
    # 5. Get results
    # 6. Verify affected_customers > 0
    # 7. Verify decision_changes has approved_to_rejected > 0
    # 8. Export CSV
    # 9. Verify CSV has 500 rows
```

**Step 2: Run test**

```bash
pytest tests/test_e2e_pipeline.py -v
```

**Step 3: Commit**

```bash
git commit -m "test: add end-to-end integration test for full pipeline"
```

---

### Task 7.2: Docker Compose Setup

**Files:**
- Create: `docker-compose.yml`
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`

**Step 1: Create docker-compose.yml**

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: policy_impact_engine
      POSTGRES_PASSWORD: postgres
    ports: ["5432:5432"]

  redis:
    image: redis:7
    ports: ["6379:6379"]

  backend:
    build: ./backend
    ports: ["8000:8000"]
    depends_on: [db, redis]
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/policy_impact_engine
      REDIS_URL: redis://redis:6379/0

  celery:
    build: ./backend
    command: celery -A app.celery_app worker --loglevel=info
    depends_on: [db, redis]

  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on: [backend]
```

**Step 2: Create Dockerfiles**

**Step 3: Test full stack**

```bash
docker-compose up --build
# Verify: frontend at localhost:3000, backend at localhost:8000
```

**Step 4: Commit**

```bash
git commit -m "feat: add Docker Compose for full stack deployment"
```

---

### Task 7.3: Seed Demo Data

**Files:**
- Create: `backend/scripts/seed_demo.py`

**Step 1: Create seed script**

Script that:
1. Uploads all 4 sample BRDs
2. Uploads both sample datasets
3. Runs pipeline for BRD-001 with auto-approve
4. Runs pipeline for BRD-004 with auto-approve
5. Creates a comparison scenario between them

**Step 2: Run seed**

```bash
cd backend
python scripts/seed_demo.py
```

**Step 3: Commit**

```bash
git commit -m "feat: add demo seed script for instant demo setup"
```

---

## Summary of Phases

| Phase | Tasks | Focus |
|-------|-------|-------|
| **Phase 1** | 1.1-1.3 | Project scaffolding, DB models, schemas |
| **Phase 2** | 2.1-2.2 | Sample data generation, sample BRDs |
| **Phase 3** | 3.1-3.4 | Core CRUD APIs (BRDs, datasets, simulations, rules) |
| **Phase 4** | 4.1-4.7 | LangGraph pipeline (parser, extractor, validator, compiler, simulator) |
| **Phase 5** | 5.1-5.8 | Frontend (all 8 pages with components) |
| **Phase 6** | 6.1-6.4 | Export, dashboard API, Celery async |
| **Phase 7** | 7.1-7.3 | E2E tests, Docker, demo seed |

**Total: 24 tasks across 7 phases**

Each phase builds on the previous. Phases 1-4 are backend-focused and can be fully tested via pytest before touching the frontend. Phase 5 is frontend-only. Phase 6-7 are integration and polish.
