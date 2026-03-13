# Policy Impact Engine - Design Document

**Date:** 2026-03-13
**Status:** Approved
**Author:** Vishnu + Claude

---

## 1. Overview

The Policy Impact Engine is a standalone platform that evaluates the impact of business rules defined in BRD documents (PDF/Word) on customer-level data before those rules are deployed to production. It targets lending/credit decisioning as the primary domain, with an extensible architecture for other domains.

**Core value proposition:** Simulate policy changes against real customer data, see who gets affected, and make informed decisions before committing to production.

## 2. Architecture

### Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | Next.js 14 + TypeScript | UI, dashboards, charts |
| Charts | Recharts or Tremor | Impact visualizations, Sankey diagrams |
| Backend | FastAPI (Python) | REST API, file handling |
| AI Orchestration | LangGraph | Multi-step BRD processing pipeline |
| Doc Parsing | LangChain doc loaders + unstructured | PDF/Word parsing |
| LLM | Claude API (via Anthropic SDK) | Rule extraction, validation, conflict detection |
| Simulation | Pandas | In-memory rule execution & comparison |
| Task Queue | Celery + Redis | Async simulation jobs |
| Database | PostgreSQL | Rules, datasets, results, versioning |
| File Storage | Local filesystem (S3-ready) | BRD files, uploaded datasets |
| Export | ReportLab (PDF) + native CSV | Stakeholder reports |

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js)                       │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌──────────────────┐  │
│  │ BRD      │ │ Rule     │ │ Dataset   │ │ Impact           │  │
│  │ Upload   │ │ Review   │ │ Manager   │ │ Dashboard        │  │
│  │ Page     │ │ Editor   │ │ Page      │ │ & Comparison     │  │
│  └──────────┘ └──────────┘ └───────────┘ └──────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │ REST API
┌────────────────────────▼────────────────────────────────────────┐
│                      BACKEND (FastAPI)                          │
│                                                                 │
│  ┌─────────────────── LangGraph Pipeline ──────────────────┐   │
│  │  Document Parser → Rule Extractor → Rule Validator      │   │
│  │       → Human Review Checkpoint → Rule Compiler         │   │
│  │       → Simulation Engine → Impact Analyzer             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Pandas Engine │ Celery Workers │ Redis State │ File Storage    │
│                                                                 │
│  ┌──────────────────── PostgreSQL ──────────────────────────┐   │
│  │  BRDs │ RuleSets │ Rules │ Datasets │ Simulations       │   │
│  │  SimulationResults │ Scenarios                           │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. User uploads BRD (PDF/Word) + customer dataset (CSV/JSON)
2. LangGraph pipeline: parse document → extract rules → validate → human review checkpoint
3. User approves/edits extracted rules in the Rule Review Editor
4. Rule Compiler converts approved rules to executable Pandas expressions
5. Simulation Engine runs rules against dataset (before vs after)
6. Impact Analyzer produces comparative statistics, segment breakdowns, financial projections
7. Results displayed on Impact Dashboard with export options

## 3. LangGraph Pipeline

### Graph Nodes

**Document Parser Node**
- Uses LangChain doc loaders (PyPDF2, python-docx) + unstructured
- Splits BRD into logical sections (eligibility criteria, pricing rules, caps, thresholds)
- Outputs: `List[DocumentSection]`

**Rule Extractor Node**
- LLM (Claude) analyzes each section and extracts structured rules
- Uses structured output with the `RuleDefinition` schema
- Outputs: `List[RuleDefinition]`

**Rule Validator Node**
- Checks rule completeness (all conditions have corresponding actions)
- Detects conflicts between rules (e.g., Rule A approves, Rule B rejects same customer profile)
- Flags ambiguous or low-confidence extractions
- Outputs: `ValidationResult` with warnings and conflicts

**Human Review Checkpoint**
- LangGraph interrupt — pauses pipeline and returns extracted rules to the UI
- User can approve, edit, delete, or add rules
- Supports sending rules back to the Extractor for re-processing

**Rule Compiler Node**
- Converts `RuleDefinition` conditions/actions into executable Pandas expressions
- Sandboxed execution — only allows DataFrame operations, no arbitrary code
- Outputs: `List[CompiledRule]` with Pandas-compatible expressions

**Simulation Engine Node**
- Phase 1 (Baseline): Apply current/default rules to establish "before" state
- Phase 2 (Simulation): Apply new rules from BRD
- Phase 3 (Comparison): Diff baseline vs simulated per customer
- Outputs: `SimulationResult` with before/after DataFrames

**Impact Analyzer Node**
- Aggregates: total affected, decision flips, amount changes
- Segment breakdown: by risk band, bureau score range, income bracket, city tier
- Financial impact: exposure change, revenue impact, loss projection
- Outputs: `ImpactAnalysis`

### Pipeline State Schema

```python
class PipelineState(TypedDict):
    # Inputs
    brd_document: bytes
    brd_filename: str
    dataset_id: str
    scenario_name: str

    # Pipeline outputs
    parsed_sections: List[DocumentSection]
    extracted_rules: List[RuleDefinition]
    validation_result: ValidationResult
    human_approved: bool
    compiled_rules: List[CompiledRule]
    simulation_result: SimulationResult
    impact_analysis: ImpactAnalysis

    # Versioning
    rule_version: int
    simulation_version: int
```

### RuleDefinition Schema

```python
class RuleType(str, Enum):
    ELIGIBILITY = "ELIGIBILITY"
    PRICING = "PRICING"
    CAP = "CAP"
    THRESHOLD = "THRESHOLD"
    SCORING = "SCORING"

class Condition(BaseModel):
    field: str                  # e.g., "bureau_score", "dti_ratio"
    operator: str               # e.g., ">=", "<=", "==", "in", "between"
    value: Any                  # e.g., 720, [0.0, 0.35], ["TIER_1", "TIER_2"]
    logic: str = "AND"          # AND | OR for chaining

class Action(BaseModel):
    action_type: str            # SET | REJECT | ADJUST | FLAG
    target_field: str           # e.g., "decision_status", "interest_rate"
    value: Any                  # e.g., "REJECTED", 0.015 (delta)
    description: str            # Human-readable action description

class RuleDefinition(BaseModel):
    rule_id: str
    rule_name: str
    description: str
    rule_type: RuleType
    conditions: List[Condition]
    actions: List[Action]
    priority: int
    source_section: str
    confidence: float
```

## 4. Database Schema

### Tables

**brd_documents**
- id (UUID, PK)
- filename (str)
- file_path (str)
- file_type (enum: PDF, DOCX)
- parsed_content (text) — raw extracted text
- metadata (JSON) — page count, author, etc.
- created_at (datetime)

**rule_sets**
- id (UUID, PK)
- brd_document_id (UUID, FK → brd_documents)
- version (int) — increments on each edit
- name (str)
- description (text)
- status (enum: DRAFT, REVIEWED, APPROVED, ARCHIVED)
- created_at (datetime)

**rules**
- id (UUID, PK)
- rule_set_id (UUID, FK → rule_sets)
- rule_id (str) — e.g., "RULE-001"
- rule_name (str)
- description (text)
- rule_type (enum: ELIGIBILITY, PRICING, CAP, THRESHOLD, SCORING)
- conditions (JSON) — List[Condition]
- actions (JSON) — List[Action]
- priority (int)
- confidence (float)
- compiled_expression (text) — Pandas expression
- source_section (str) — BRD reference
- has_conflicts (bool)
- conflict_details (JSON)
- created_at (datetime)

**datasets**
- id (UUID, PK)
- name (str)
- description (text)
- file_path (str)
- file_type (enum: CSV, JSON)
- row_count (int)
- column_schema (JSON) — detected column names, types, ranges
- sample_data (JSON) — first 10 rows for preview
- data_profile (JSON) — distributions, nulls, ranges
- created_at (datetime)

**simulations**
- id (UUID, PK)
- scenario_name (str)
- dataset_id (UUID, FK → datasets)
- rule_set_id (UUID, FK → rule_sets)
- version (int)
- status (enum: PENDING, RUNNING, COMPLETED, FAILED)
- parameters (JSON) — sensitivity overrides, config
- created_at (datetime)
- completed_at (datetime)

**simulation_results**
- id (UUID, PK)
- simulation_id (UUID, FK → simulations)
- summary_stats (JSON) — totals, percentages, counts
- segment_analysis (JSON) — breakdown by risk band, income, etc.
- customer_diffs (JSON or file path) — per-customer before/after
- financial_impact (JSON) — exposure, revenue, loss estimates
- conflict_report (JSON) — rules that conflicted during simulation
- created_at (datetime)

**scenarios**
- id (UUID, PK)
- name (str)
- description (text)
- simulation_ids (JSON array of UUIDs)
- comparison_result (JSON) — precomputed comparison
- created_at (datetime)

## 5. Simulation Engine

### Phase 1 — Baseline
Run current/default rules against dataset to establish the "before" state.
```python
baseline_df = dataset_df.copy()
baseline_df["decision"] = apply_current_rules(baseline_df)
baseline_df["eligible_amount"] = calculate_current_caps(baseline_df)
baseline_df["interest_rate"] = calculate_current_pricing(baseline_df)
```

### Phase 2 — Simulation
Apply new/modified rules from the BRD in priority order.
```python
simulated_df = dataset_df.copy()
for rule in sorted(compiled_rules, key=lambda r: r.priority):
    mask = rule.evaluate_conditions(simulated_df)  # Pandas boolean mask
    simulated_df.loc[mask] = rule.apply_actions(simulated_df.loc[mask])
```

### Phase 3 — Comparison
Diff baseline vs simulated.
```python
impact = {
    "total_customers": len(dataset_df),
    "affected_customers": (baseline_df != simulated_df).any(axis=1).sum(),
    "decision_changes": {
        "approved_to_rejected": count,
        "rejected_to_approved": count,
        "conditions_added": count,
        "conditions_removed": count,
    },
    "amount_changes": {
        "increased": count,
        "decreased": count,
        "avg_delta": mean,
    },
    "segment_breakdown": {
        "by_risk_band": {...},
        "by_bureau_score_range": {...},
        "by_income_bracket": {...},
        "by_city_tier": {...},
    },
    "financial_impact": {
        "total_exposure_change": delta,
        "avg_loan_amount_change": delta,
        "revenue_impact_estimate": delta,
        "expected_loss_change": delta,
    }
}
```

### Rule Conflict Detection
During simulation, if two rules produce contradictory outcomes for the same customer:
- Log the conflict with both rule IDs and the affected customer count
- Use the higher-priority rule's action
- Flag in the conflict report for human review

### Sensitivity Analysis
Users can adjust numeric thresholds in rules via UI sliders:
- Each adjustment creates a temporary modified rule set
- Re-runs simulation with the tweaked values
- Shows delta compared to the original BRD simulation

## 6. Frontend Pages

### 6.1 Dashboard (Home)
- Recent simulations with status indicators
- Quick stats: BRDs processed, simulations run, average impact rate
- Quick-access to recent scenarios

### 6.2 BRD Upload & Processing
- Drag-and-drop PDF/Word upload
- LangGraph step indicator (parsing → extracting → validating)
- Real-time rule extraction preview

### 6.3 Rule Review & Editor
- Table of extracted rules with confidence scores
- Expandable rows: conditions/actions in natural language + compiled form
- Conflict detection panel (red highlights with explanations)
- Edit/delete/add rules manually
- Approve/reject per rule
- Version history sidebar

### 6.4 Dataset Manager
- Upload CSV/JSON
- Auto-detected column schema with preview
- Data profiling: distributions, null counts, value ranges
- Sample data viewer (first 20 rows)

### 6.5 Simulation Runner
- Select rule set + dataset
- Name the scenario
- Sensitivity sliders for numeric thresholds
- Run button with progress indicator

### 6.6 Impact Dashboard
- Summary cards: total affected, decision flips, amount changes
- Before/after distribution charts (histograms of bureau scores, DTI, amounts)
- Sankey diagram: customer flow between decision states
- Segment breakdown table
- Financial impact panel
- Customer-level diff table (searchable, filterable)

### 6.7 Scenario Comparison
- Select 2-3 scenarios to compare
- Side-by-side overlay charts
- Delta tables highlighting differences
- "Winner" indicators per metric

### 6.8 Export & Reporting
- PDF report generation (executive summary + charts + tables)
- CSV export for raw simulation results
- Per-scenario and comparison reports

## 7. Sample BRDs & Test Data

### BRD-001: DTI Cap Tightening
- Reduce DTI cap from 0.40 to 0.35 for unsecured personal loans
- Increase minimum bureau score from 700 to 720
- Reject if recent inquiries > 3 in last 3 months
- Expected: ~15-20% reduction in approval rate

### BRD-002: Income Verification Enhancement
- Minimum monthly income of 50,000 for loans > 150,000
- Salary consistency score must be > 0.85 (up from 0.80)
- Banking stability index minimum raised to 0.75
- Expected: tighter eligibility for higher amounts

### BRD-003: Pricing Tier Restructure
- New risk-based pricing tiers (Tier 1-5 replacing Tier 1-3)
- Bureau score 750+ gets 50bps rate reduction
- >2 active unsecured loans get 100bps surcharge
- Expected: rate redistribution, better pricing for strong profiles

### BRD-004: Post-COVID Risk Tightening (Rejection Scenario)
- Minimum bureau score raised to 750 (from 700)
- DTI cap reduced to 0.30 (from 0.40)
- No loans for employment tenure < 24 months
- Self-employed applicants capped at 100,000 loan amount
- Cash deposit ratio > 20% triggers rejection
- Expected: 40-50% rejection increase — demonstrates negative impact clearly

### Sample Datasets
- **Dataset 1:** 500 customer loan applications (CSV) with realistic distributions
- **Dataset 2:** 200 concurrent borrowers (JSON) for repeat loan testing

### Enhanced Customer Schema (expanded from provided request/response JSONs)
Fields include: customer demographics, employment details, banking behavior (UPI/IMPS/NEFT volumes, salary consistency, balance trends), bureau data (score, active/closed loans, utilization, DPD history), calculated scores (G5, G6 sub-models), and decision context (policy caps, risk segment, pricing tier).

## 8. Key Design Decisions

1. **LangGraph over LangChain chains** — stateful pipeline with human-in-loop support, retry logic, and conditional branching
2. **Pandas over SQL for simulation** — faster iteration for MVP, in-memory execution, rich comparison capabilities. SQL can be added later for scale.
3. **Claude as the LLM** — strong structured output, document understanding, and reasoning for rule extraction and conflict detection
4. **Versioned rule sets** — every edit creates a new version, enabling history tracking and rollback
5. **Scenario-based comparison** — first-class concept allowing multiple BRD variations to be tested against the same dataset
6. **Sensitivity analysis** — allows fine-tuning thresholds without re-uploading BRDs, enabling rapid what-if exploration
7. **Rule conflict detection** — proactive identification of contradictory rules before simulation, reducing false results
