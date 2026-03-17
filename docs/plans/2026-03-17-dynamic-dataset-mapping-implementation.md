# Dynamic Dataset Column Mapping — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow datasets with different column names to work with the simulation engine via auto-detected, user-reviewable column mappings and per-dataset baseline configuration.

**Architecture:** Two new JSON columns on the Dataset model (column_mapping, baseline_config). A column detector service auto-maps on upload. A mapper module renames columns to canonical names before the engine runs. Engine internals stay unchanged — config is passed as optional params.

**Tech Stack:** Python/FastAPI (backend), Next.js/React (frontend), SQLAlchemy, Pandas, shadcn/ui

---

### Task 1: Add Dataset Model Columns

**Files:**
- Modify: `backend/app/models/dataset.py`

**Step 1: Add column_mapping and baseline_config fields**

```python
# Add after the existing data_profile column (line 26)
column_mapping: Mapped[dict | None] = mapped_column(JSON, nullable=True)
baseline_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

**Step 2: Restart backend to recreate tables**

Run: `# Backend auto-reloads via uvicorn --reload`
Expected: Tables recreated with new columns (dev mode drops/recreates)

**Step 3: Commit**

```bash
git add backend/app/models/dataset.py
git commit -m "feat: add column_mapping and baseline_config to Dataset model"
```

---

### Task 2: Update Dataset Schemas

**Files:**
- Modify: `backend/app/schemas/dataset.py`

**Step 1: Add mapping fields to response schemas**

```python
# Add to DatasetProfileResponse (after sample_data)
column_mapping: dict | None = None
baseline_config: dict | None = None

# Add new request schema
class DatasetMappingRequest(BaseModel):
    column_mapping: dict
    baseline_config: dict | None = None

# Add to DatasetListResponse
column_mapping: dict | None = None

# Add to DatasetUploadResponse
column_mapping: dict | None = None
```

**Step 2: Commit**

```bash
git add backend/app/schemas/dataset.py
git commit -m "feat: add column_mapping schemas for dataset mapping API"
```

---

### Task 3: Create Column Detector Service

**Files:**
- Create: `backend/app/services/column_detector.py`
- Create: `backend/tests/services/test_column_detector.py`

**Step 1: Write tests for column detection**

```python
# backend/tests/services/test_column_detector.py
import pandas as pd
import pytest
from app.services.column_detector import detect_mapping

def test_detect_exact_column_names():
    """Standard columns should be detected with 100% confidence."""
    df = pd.DataFrame({
        "bureau_score": [750, 680],
        "monthly_income": [50000, 30000],
        "desired_amount": [500000, 200000],
        "dti_ratio": [0.3, 0.45],
        "region": ["North", "South"],
    })
    result = detect_mapping(df)
    assert result["score_field"]["column"] == "bureau_score"
    assert result["income_field"]["column"] == "monthly_income"
    assert result["amount_field"]["column"] == "desired_amount"
    assert result["dti_field"]["column"] == "dti_ratio"
    assert result["score_field"]["confidence"] == 1.0


def test_detect_aliased_column_names():
    """Common aliases should be detected."""
    df = pd.DataFrame({
        "cibil_score": [750, 680],
        "net_salary": [50000, 30000],
        "loan_amount": [500000, 200000],
        "debt_to_income": [0.3, 0.45],
    })
    result = detect_mapping(df)
    assert result["score_field"]["column"] == "cibil_score"
    assert result["income_field"]["column"] == "net_salary"
    assert result["amount_field"]["column"] == "loan_amount"
    assert result["dti_field"]["column"] == "debt_to_income"


def test_detect_with_statistical_validation():
    """Score field should be validated by value range."""
    df = pd.DataFrame({
        "score": [750, 680, 820],
        "income": [50000, 30000, 80000],
        "amount": [500000, 200000, 1000000],
        "dti": [0.3, 0.45, 0.2],
    })
    result = detect_mapping(df)
    assert result["score_field"]["column"] == "score"
    assert result["score_field"]["confidence"] >= 0.7


def test_detect_segmentation_fields():
    """Categorical columns with few unique values should be suggested."""
    df = pd.DataFrame({
        "bureau_score": [750],
        "monthly_income": [50000],
        "desired_amount": [500000],
        "dti_ratio": [0.3],
        "region": ["North"],
        "product_type": ["Home Loan"],
        "applicant_id": ["APP-0001"],
    })
    result = detect_mapping(df)
    seg = result.get("segmentation_fields", {})
    assert "region" in seg or "product_type" in seg


def test_detect_dti_auto_normalize():
    """DTI values 0-100 should be flagged for normalization."""
    df = pd.DataFrame({
        "bureau_score": [750],
        "monthly_income": [50000],
        "desired_amount": [500000],
        "dti_pct": [35.0],
    })
    result = detect_mapping(df)
    assert result["dti_field"]["column"] == "dti_pct"
    assert result["dti_field"].get("needs_normalization") is True


def test_detect_unmatched_returns_none():
    """Columns that don't match anything should not be assigned."""
    df = pd.DataFrame({
        "foo": [1, 2],
        "bar": [3, 4],
        "baz": [5, 6],
        "qux": [0.1, 0.2],
    })
    result = detect_mapping(df)
    unmatched = [k for k in ["score_field", "income_field", "amount_field", "dti_field"]
                 if result[k]["column"] is None]
    assert len(unmatched) > 0
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/services/test_column_detector.py -v`
Expected: FAIL (module not found)

**Step 3: Implement column detector**

```python
# backend/app/services/column_detector.py
import pandas as pd

FIELD_ALIASES: dict[str, list[str]] = {
    "score_field": [
        "bureau_score", "cibil_score", "credit_score", "fico_score",
        "score", "risk_score", "credit_rating", "bureau",
    ],
    "income_field": [
        "monthly_income", "net_salary", "salary", "income",
        "monthly_salary", "net_income", "gross_income", "annual_income",
    ],
    "amount_field": [
        "desired_amount", "loan_amount", "requested_amount", "amount",
        "principal", "loan_value", "sanctioned_amount", "applied_amount",
    ],
    "dti_field": [
        "dti_ratio", "dti", "debt_to_income", "debt_ratio",
        "dti_pct", "debt_income_ratio",
    ],
}

# Statistical validation ranges
FIELD_VALIDATORS: dict[str, dict] = {
    "score_field": {"min": 100, "max": 1000, "typical_min": 300, "typical_max": 900},
    "income_field": {"min": 0, "max": 100_000_000},
    "amount_field": {"min": 0, "max": 1_000_000_000},
    "dti_field": {"min": 0, "max": 100},
}


def detect_mapping(df: pd.DataFrame) -> dict:
    """Auto-detect column mapping from a DataFrame.

    Returns a dict with keys: score_field, income_field, amount_field, dti_field,
    segmentation_fields. Each required field has: column, confidence, reason,
    and optionally needs_normalization.
    """
    result = {}
    used_columns: set[str] = set()
    numeric_cols = list(df.select_dtypes(include="number").columns)

    for field_key, aliases in FIELD_ALIASES.items():
        best = _find_best_match(df, field_key, aliases, numeric_cols, used_columns)
        result[field_key] = best
        if best["column"]:
            used_columns.add(best["column"])

    # Detect segmentation fields
    result["segmentation_fields"] = _detect_segmentation(df, used_columns)

    return result


def _find_best_match(
    df: pd.DataFrame,
    field_key: str,
    aliases: list[str],
    numeric_cols: list[str],
    used_columns: set[str],
) -> dict:
    """Find best matching column for a field."""
    col_names_lower = {c.lower().replace(" ", "_"): c for c in df.columns}

    # Pass 1: Exact alias match
    for alias in aliases:
        if alias in col_names_lower and col_names_lower[alias] not in used_columns:
            col = col_names_lower[alias]
            confidence = 1.0 if alias == aliases[0] else 0.9
            validated = _validate_statistically(df[col], field_key)
            if validated["valid"]:
                return {
                    "column": col,
                    "confidence": confidence,
                    "reason": f"Exact match: '{col}' matches alias '{alias}'",
                    **_normalization_info(df[col], field_key),
                }

    # Pass 2: Substring match
    for alias in aliases:
        for col_lower, col_orig in col_names_lower.items():
            if col_orig in used_columns:
                continue
            if alias in col_lower or col_lower in alias:
                validated = _validate_statistically(df[col_orig], field_key)
                if validated["valid"]:
                    return {
                        "column": col_orig,
                        "confidence": 0.7,
                        "reason": f"Partial match: '{col_orig}' ~ '{alias}'",
                        **_normalization_info(df[col_orig], field_key),
                    }

    # Pass 3: Statistical heuristic for unmatched numeric columns
    validators = FIELD_VALIDATORS.get(field_key, {})
    if validators:
        for col in numeric_cols:
            if col in used_columns:
                continue
            series = df[col].dropna()
            if len(series) == 0:
                continue
            col_min, col_max = float(series.min()), float(series.max())
            if validators.get("min", float("-inf")) <= col_min and col_max <= validators.get("max", float("inf")):
                if field_key == "dti_field" and col_max <= 1.0:
                    return {
                        "column": col,
                        "confidence": 0.5,
                        "reason": f"Statistical match: values {col_min:.2f}-{col_max:.2f} fit {field_key}",
                    }

    return {"column": None, "confidence": 0.0, "reason": "No match found"}


def _validate_statistically(series: pd.Series, field_key: str) -> dict:
    """Check if column values are statistically plausible for the field."""
    validators = FIELD_VALIDATORS.get(field_key, {})
    if not validators:
        return {"valid": True}

    if not pd.api.types.is_numeric_dtype(series):
        if field_key in ("score_field", "income_field", "amount_field", "dti_field"):
            return {"valid": False, "reason": "Not numeric"}
        return {"valid": True}

    clean = series.dropna()
    if len(clean) == 0:
        return {"valid": False, "reason": "All null"}

    col_min = float(clean.min())
    col_max = float(clean.max())

    if col_min < validators.get("min", float("-inf")):
        return {"valid": False, "reason": f"Min {col_min} below expected {validators['min']}"}
    if col_max > validators.get("max", float("inf")):
        return {"valid": False, "reason": f"Max {col_max} above expected {validators['max']}"}

    return {"valid": True}


def _normalization_info(series: pd.Series, field_key: str) -> dict:
    """Check if DTI values need normalization (0-100 -> 0-1)."""
    if field_key != "dti_field":
        return {}
    clean = series.dropna()
    if len(clean) == 0:
        return {}
    if float(clean.max()) > 1.0:
        return {"needs_normalization": True}
    return {}


def _detect_segmentation(df: pd.DataFrame, used_columns: set[str]) -> dict:
    """Detect categorical columns suitable for segmentation."""
    seg_fields = {}
    for col in df.columns:
        if col in used_columns:
            continue
        if df[col].dtype == "object" or str(df[col].dtype) == "category":
            nunique = df[col].nunique()
            if 2 <= nunique <= 20:
                seg_fields[col] = {
                    "unique_values": nunique,
                    "sample_values": df[col].dropna().unique()[:5].tolist(),
                }
    return seg_fields


def get_default_baseline_config() -> dict:
    """Return the default baseline configuration."""
    return {
        "min_score": 700,
        "max_dti": 0.40,
        "min_income": 25000,
        "rate_tiers": [[800, 999, 0.105], [750, 799, 0.12], [720, 749, 0.135], [700, 719, 0.155]],
        "default_rate": 0.175,
        "origination_fee_rate": 0.02,
        "loan_tenure_years": 3,
        "lgd": 0.40,
        "pd_tiers": [[800, 999, 0.01], [750, 799, 0.03], [720, 749, 0.05], [700, 719, 0.08], [650, 699, 0.12], [0, 649, 0.15]],
    }
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/services/test_column_detector.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add backend/app/services/column_detector.py backend/tests/services/test_column_detector.py
git commit -m "feat: add auto-detection column mapping service"
```

---

### Task 4: Create Column Mapper Module

**Files:**
- Create: `backend/app/simulation/mapper.py`
- Create: `backend/tests/simulation/test_mapper.py`

**Step 1: Write tests**

```python
# backend/tests/simulation/test_mapper.py
import pandas as pd
import pytest
from app.simulation.mapper import apply_column_mapping

def test_renames_columns_to_canonical():
    df = pd.DataFrame({
        "cibil_score": [750],
        "net_salary": [50000],
        "loan_amount": [500000],
        "debt_to_income": [0.3],
    })
    mapping = {
        "score_field": "cibil_score",
        "income_field": "net_salary",
        "amount_field": "loan_amount",
        "dti_field": "debt_to_income",
    }
    result = apply_column_mapping(df, mapping)
    assert "bureau_score" in result.columns
    assert "monthly_income" in result.columns
    assert "desired_amount" in result.columns
    assert "dti_ratio" in result.columns
    assert "cibil_score" not in result.columns


def test_no_rename_when_already_canonical():
    df = pd.DataFrame({
        "bureau_score": [750],
        "monthly_income": [50000],
        "desired_amount": [500000],
        "dti_ratio": [0.3],
    })
    mapping = {
        "score_field": "bureau_score",
        "income_field": "monthly_income",
        "amount_field": "desired_amount",
        "dti_field": "dti_ratio",
    }
    result = apply_column_mapping(df, mapping)
    assert list(result.columns) == list(df.columns)


def test_preserves_extra_columns():
    df = pd.DataFrame({
        "cibil_score": [750],
        "net_salary": [50000],
        "loan_amount": [500000],
        "debt_to_income": [0.3],
        "region": ["North"],
    })
    mapping = {
        "score_field": "cibil_score",
        "income_field": "net_salary",
        "amount_field": "loan_amount",
        "dti_field": "debt_to_income",
    }
    result = apply_column_mapping(df, mapping)
    assert "region" in result.columns


def test_none_mapping_returns_unchanged():
    df = pd.DataFrame({"bureau_score": [750], "monthly_income": [50000],
                        "desired_amount": [500000], "dti_ratio": [0.3]})
    result = apply_column_mapping(df, None)
    assert list(result.columns) == list(df.columns)


def test_normalizes_dti_percentage():
    df = pd.DataFrame({
        "bureau_score": [750],
        "monthly_income": [50000],
        "desired_amount": [500000],
        "dti_pct": [35.0],
    })
    mapping = {
        "score_field": "bureau_score",
        "income_field": "monthly_income",
        "amount_field": "desired_amount",
        "dti_field": "dti_pct",
        "dti_needs_normalization": True,
    }
    result = apply_column_mapping(df, mapping)
    assert result["dti_ratio"].iloc[0] == pytest.approx(0.35)
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/simulation/test_mapper.py -v`
Expected: FAIL

**Step 3: Implement mapper**

```python
# backend/app/simulation/mapper.py
import pandas as pd

CANONICAL_NAMES = {
    "score_field": "bureau_score",
    "income_field": "monthly_income",
    "amount_field": "desired_amount",
    "dti_field": "dti_ratio",
}


def apply_column_mapping(df: pd.DataFrame, mapping: dict | None) -> pd.DataFrame:
    """Rename dataset columns to canonical engine names.

    Args:
        df: Raw dataset DataFrame.
        mapping: Column mapping dict with keys score_field, income_field,
                 amount_field, dti_field. If None, returns df unchanged.

    Returns:
        DataFrame with canonical column names.
    """
    if not mapping:
        return df

    result = df.copy()

    rename_map = {}
    for field_key, canonical in CANONICAL_NAMES.items():
        source_col = mapping.get(field_key)
        if source_col and source_col != canonical and source_col in result.columns:
            rename_map[source_col] = canonical

    if rename_map:
        result = result.rename(columns=rename_map)

    # Normalize DTI if flagged (values 0-100 -> 0-1)
    if mapping.get("dti_needs_normalization") and "dti_ratio" in result.columns:
        result["dti_ratio"] = result["dti_ratio"] / 100.0

    return result
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/simulation/test_mapper.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add backend/app/simulation/mapper.py backend/tests/simulation/test_mapper.py
git commit -m "feat: add column mapper for canonical name translation"
```

---

### Task 5: Parameterize Baseline Config

**Files:**
- Modify: `backend/app/simulation/baseline.py`
- Create: `backend/tests/simulation/test_baseline_config.py`

**Step 1: Write tests for configurable baseline**

```python
# backend/tests/simulation/test_baseline_config.py
import pandas as pd
from app.simulation.baseline import apply_baseline

def _make_df():
    return pd.DataFrame({
        "bureau_score": [750, 680, 600],
        "monthly_income": [50000, 30000, 20000],
        "desired_amount": [500000, 200000, 100000],
        "dti_ratio": [0.3, 0.35, 0.5],
    })

def test_default_config_unchanged():
    """Without config, behavior matches original hardcoded logic."""
    df = _make_df()
    result = apply_baseline(df)
    assert result.loc[0, "baseline_decision"] == "APPROVED"
    assert result.loc[1, "baseline_decision"] == "REJECTED"  # score < 700
    assert result.loc[2, "baseline_decision"] == "REJECTED"  # score < 700 + dti > 0.4

def test_custom_lower_score_threshold():
    """Lower min_score should approve more applicants."""
    df = _make_df()
    config = {"min_score": 650, "max_dti": 0.40, "min_income": 25000}
    result = apply_baseline(df, config=config)
    assert result.loc[0, "baseline_decision"] == "APPROVED"
    assert result.loc[1, "baseline_decision"] == "APPROVED"  # 680 >= 650

def test_custom_rate_tiers():
    """Custom rate tiers should override defaults."""
    df = _make_df()
    config = {
        "min_score": 600,
        "max_dti": 0.60,
        "min_income": 15000,
        "rate_tiers": [[700, 999, 0.08], [600, 699, 0.14]],
        "default_rate": 0.20,
    }
    result = apply_baseline(df, config=config)
    assert result.loc[0, "baseline_interest_rate"] == 0.08   # 750 in [700,999]
    assert result.loc[1, "baseline_interest_rate"] == 0.14   # 680 in [600,699]
    assert result.loc[2, "baseline_interest_rate"] == 0.14   # 600 in [600,699]
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/simulation/test_baseline_config.py -v`
Expected: FAIL (apply_baseline doesn't accept config param)

**Step 3: Modify baseline.py to accept config**

Modify `apply_baseline` in `backend/app/simulation/baseline.py` to accept an optional `config` dict. Replace all hardcoded references with `config.get(key, default)`. Same for `assign_eligible_amount` and `assign_interest_rate` — they need access to rate tiers from config.

Key changes:
- `apply_baseline(df, config=None)` — reads min_score, max_dti, min_income, rate_tiers, default_rate from config
- `assign_eligible_amount(row)` — no change needed (uses monthly_income directly)
- `assign_interest_rate(row, rate_tiers=None, default_rate=None)` — accepts optional rate tiers

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/simulation/test_baseline_config.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add backend/app/simulation/baseline.py backend/tests/simulation/test_baseline_config.py
git commit -m "feat: parameterize baseline rules with optional config"
```

---

### Task 6: Parameterize Comparator Config

**Files:**
- Modify: `backend/app/simulation/comparator.py`

**Step 1: Modify comparator to accept config**

Update `compare_results` to accept optional `config` dict. Pass it through to `_calculate_financial_impact` and `_build_segment_breakdown`. Extract PD_TIERS, LGD, LOAN_TENURE_YEARS, ORIGINATION_FEE_RATE from config with fallback to current module-level constants.

Key changes:
- `compare_results(baseline_df, simulated_df, conflict_log, config=None)`
- `_calculate_financial_impact(...)` reads pd_tiers, lgd, loan_tenure_years, origination_fee_rate from config
- `_build_segment_breakdown(...)` reads loan_tenure_years from config
- `_get_pd(score, pd_tiers=None)` accepts optional pd_tiers list

**Step 2: Verify existing behavior unchanged**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests PASS (None config = use defaults)

**Step 3: Commit**

```bash
git add backend/app/simulation/comparator.py
git commit -m "feat: parameterize comparator with optional financial config"
```

---

### Task 7: Wire Config Through Engine and Pipeline

**Files:**
- Modify: `backend/app/simulation/engine.py`
- Modify: `backend/app/pipeline/graph.py`
- Modify: `backend/app/tasks/simulation_task.py`

**Step 1: Update engine.py**

Add `config=None` param to `run_simulation`. Pass it to `apply_baseline` and `compare_results`. Also pass rate_tiers to `assign_interest_rate` for REJECTED→APPROVED transitions.

```python
def run_simulation(df, new_rules, config=None):
    baseline_df = apply_baseline(df, config=config)
    ...
    # Phase 2b: use config rate tiers for flipped applicants
    ...
    return compare_results(baseline_df, simulated_df, conflict_log, config=config)
```

**Step 2: Update graph.py**

Add `baseline_config` to `PipelineState`. Thread it through `simulation_node` to `run_simulation`.

**Step 3: Update simulation_task.py**

Load dataset's `column_mapping` and `baseline_config` from DB. Apply `apply_column_mapping` to the DataFrame before running pipeline. Pass `baseline_config` into `run_pipeline`.

```python
# After reading dataset_df:
from app.simulation.mapper import apply_column_mapping
# Load mapping from DB
dataset = session.get(Dataset, uuid.UUID(dataset_id))  # need dataset_id param
if dataset and dataset.column_mapping:
    dataset_df = apply_column_mapping(dataset_df, dataset.column_mapping)
baseline_config = dataset.baseline_config if dataset else None

result = run_pipeline(
    brd_content=brd_content,
    brd_filename=brd_filename,
    dataset_df=dataset_df,
    auto_approve=True,
    baseline_config=baseline_config,
)
```

**Step 4: Run all tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/app/simulation/engine.py backend/app/pipeline/graph.py backend/app/tasks/simulation_task.py
git commit -m "feat: wire baseline config through engine, pipeline, and task"
```

---

### Task 8: Add Mapping API Endpoints

**Files:**
- Modify: `backend/app/api/v1/datasets.py`
- Modify: `backend/app/services/dataset_service.py`

**Step 1: Add detect-mapping endpoint**

```python
@router.get("/{dataset_id}/detect-mapping")
async def detect_mapping_endpoint(dataset_id: str, db: AsyncSession = Depends(get_db)):
    ds = await dataset_service.get_dataset(dataset_id, db)
    if not ds:
        raise HTTPException(404, "Dataset not found")
    mapping = await dataset_service.detect_column_mapping(ds)
    return mapping
```

**Step 2: Add save-mapping endpoint**

```python
@router.put("/{dataset_id}/mapping")
async def save_mapping(
    dataset_id: str,
    request: DatasetMappingRequest,
    db: AsyncSession = Depends(get_db),
):
    ds = await dataset_service.get_dataset(dataset_id, db)
    if not ds:
        raise HTTPException(404, "Dataset not found")
    # Validate all 4 required fields are mapped
    required = ["score_field", "income_field", "amount_field", "dti_field"]
    for field in required:
        if not request.column_mapping.get(field):
            raise HTTPException(400, f"Required field '{field}' not mapped")
    updated = await dataset_service.save_mapping(ds, request.column_mapping, request.baseline_config, db)
    return {"status": "saved", "column_mapping": updated.column_mapping, "baseline_config": updated.baseline_config}
```

**Step 3: Add service functions in dataset_service.py**

```python
async def detect_column_mapping(dataset: Dataset) -> dict:
    """Run auto-detection on a dataset."""
    from app.services.column_detector import detect_mapping, get_default_baseline_config
    df = pd.read_csv(dataset.file_path) if dataset.file_type == DatasetFileType.CSV else pd.read_json(dataset.file_path)
    detected = detect_mapping(df)
    detected["default_baseline_config"] = get_default_baseline_config()
    return detected


async def save_mapping(dataset: Dataset, column_mapping: dict, baseline_config: dict | None, db: AsyncSession) -> Dataset:
    """Save column mapping and baseline config."""
    dataset.column_mapping = column_mapping
    dataset.baseline_config = baseline_config
    await db.commit()
    await db.refresh(dataset)
    return dataset
```

**Step 4: Commit**

```bash
git add backend/app/api/v1/datasets.py backend/app/services/dataset_service.py
git commit -m "feat: add detect-mapping and save-mapping API endpoints"
```

---

### Task 9: Update Frontend Types

**Files:**
- Modify: `frontend/src/lib/types.ts`

**Step 1: Add mapping fields to Dataset interface**

```typescript
// Add to Dataset interface after data_profile
column_mapping: Record<string, any> | null;
baseline_config: Record<string, any> | null;
```

**Step 2: Commit**

```bash
git add frontend/src/lib/types.ts
git commit -m "feat: add column_mapping and baseline_config to Dataset type"
```

---

### Task 10: Create Mapping Form Component

**Files:**
- Create: `frontend/src/components/datasets/mapping-form.tsx`

**Step 1: Build the mapping form**

Component that receives:
- `columns: string[]` — available column names from dataset schema
- `detectedMapping: Record<string, any>` — auto-detected mapping with confidence
- `onSave: (mapping, config) => void` — callback when user saves

UI elements:
- 4 required field dropdowns (Score, Income, Amount, DTI) pre-filled from detection
- Confidence badge next to each (green >80%, yellow >50%, red <50%)
- Segmentation fields section with add/remove
- Baseline config section with number inputs (min score, max DTI, min income)
- Rate tiers table (editable)
- Save button (disabled until all 4 required fields mapped to distinct columns)

Use shadcn Select, Input, Button, Card, Badge, Label components.

**Step 2: Commit**

```bash
git add frontend/src/components/datasets/mapping-form.tsx
git commit -m "feat: add column mapping form component"
```

---

### Task 11: Integrate Mapping Into Dataset Detail Page

**Files:**
- Modify: `frontend/src/app/datasets/[id]/page.tsx`

**Step 1: Add Mapping tab**

Add a new "Column Mapping" tab to the existing Tabs component. When selected:
1. Fetch `GET /datasets/{id}/detect-mapping` to get auto-detected mapping
2. If dataset already has `column_mapping`, show saved mapping as pre-filled
3. Render `MappingForm` component
4. On save, `PUT /datasets/{id}/mapping`
5. Show success toast

Add a mapping status badge in the header: "Mapped" (green) or "Unmapped" (yellow).

**Step 2: Commit**

```bash
git add frontend/src/app/datasets/[id]/page.tsx
git commit -m "feat: add column mapping tab to dataset detail page"
```

---

### Task 12: Block Simulation for Unmapped Datasets

**Files:**
- Modify: `frontend/src/app/simulations/new/page.tsx`
- Modify: `backend/app/api/v1/pipeline.py` (optional server-side guard)

**Step 1: Frontend guard**

When user selects a dataset in the simulation form, check if `column_mapping` is null. If so, show a warning and disable the "Run Simulation" button with a link to the dataset mapping page.

**Step 2: Backend guard (optional)**

In the pipeline run endpoint, check if the dataset has `column_mapping`. If null, return 400 with message "Dataset columns must be mapped before running a simulation."

**Step 3: Commit**

```bash
git add frontend/src/app/simulations/new/page.tsx backend/app/api/v1/pipeline.py
git commit -m "feat: block simulation for unmapped datasets"
```

---

### Task 13: Update Dataset Upload Response

**Files:**
- Modify: `backend/app/api/v1/datasets.py`

**Step 1: Auto-detect on upload**

After uploading, automatically run detection and store the result as a "suggested" mapping (but don't save it to `column_mapping` — user must confirm). Include the detected mapping in the upload response so the frontend can redirect to the mapping step.

```python
# In upload_dataset endpoint, after ds = await dataset_service.upload_dataset(...)
detected = await dataset_service.detect_column_mapping(ds)
return DatasetUploadResponse(
    ...
    detected_mapping=detected,
)
```

**Step 2: Commit**

```bash
git add backend/app/api/v1/datasets.py backend/app/schemas/dataset.py
git commit -m "feat: include auto-detected mapping in upload response"
```

---

### Task 14: End-to-End Test

**Step 1: Upload the test dataset with non-standard column names**

Create a small CSV with columns named `cibil_score`, `net_salary`, `loan_amount`, `debt_ratio` and upload via API.

**Step 2: Verify auto-detection**

Call `GET /datasets/{id}/detect-mapping` and verify all 4 fields are correctly detected.

**Step 3: Save mapping and run simulation**

Call `PUT /datasets/{id}/mapping` with the mapping, then run a simulation. Verify results are correct.

**Step 4: Test with standard column names**

Upload the existing `test_dataset_500.csv` (uses `bureau_score`, etc.). Verify detection returns 100% confidence and simulation works with mapping saved.

**Step 5: Test backward compatibility**

Verify existing datasets with `column_mapping = null` still work if the simulation service handles the null case.

**Step 6: Commit final integration**

```bash
git add -A
git commit -m "feat: complete dynamic dataset column mapping support"
```
