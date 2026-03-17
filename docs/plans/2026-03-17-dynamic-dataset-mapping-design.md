# Dynamic Dataset Column Mapping — Design Document

**Date**: 2026-03-17
**Status**: Approved
**Approach**: Column Mapping Table (Approach 1)

## Problem

The simulation engine hardcodes column names (`bureau_score`, `monthly_income`, `desired_amount`, `dti_ratio`) and baseline thresholds. Datasets from different banks/partners use different column names for the same concepts, making them incompatible without manual data preprocessing.

## Scope

- Same lending domain, varying schemas across banks/partners
- Auto-detect column mapping on upload + user review/edit
- Baseline rules (thresholds, rate tiers, PD tiers) configurable per dataset
- 4 required fields: score, income, amount, DTI ratio
- Upload fails validation if any required field can't be mapped

## Design

### 1. Data Model Changes

Two new nullable JSON columns on the `datasets` table:

**`column_mapping`**:
```json
{
  "score_field": "cibil_score",
  "income_field": "net_salary",
  "amount_field": "loan_amount",
  "dti_field": "debt_to_income",
  "segmentation_fields": {
    "region": "branch_zone",
    "employment_type": "emp_category"
  }
}
```

**`baseline_config`**:
```json
{
  "min_score": 700,
  "max_dti": 0.40,
  "min_income": 25000,
  "rate_tiers": [[800,999,0.105],[750,799,0.12],[720,749,0.135],[700,719,0.155]],
  "default_rate": 0.175,
  "origination_fee_rate": 0.02,
  "loan_tenure_years": 3,
  "lgd": 0.40,
  "pd_tiers": [[800,999,0.01],[750,799,0.03],[720,749,0.05],[700,719,0.08],[650,699,0.12],[0,649,0.15]]
}
```

Null values = use current hardcoded defaults (backward compatible).

### 2. Auto-Detection Logic

New module: `backend/app/services/column_detector.py`

**Name matching** — fuzzy match against known aliases:
- `score_field`: bureau_score, cibil_score, credit_score, fico_score, score, risk_score
- `income_field`: monthly_income, net_salary, salary, income, monthly_salary, net_income
- `amount_field`: desired_amount, loan_amount, requested_amount, amount, principal
- `dti_field`: dti_ratio, dti, debt_to_income, debt_ratio

**Statistical validation** — verify detected columns have sensible data:
- Score: numeric, values typically 300-900
- Income: numeric, positive
- Amount: numeric, positive
- DTI: numeric, 0-1 (or 0-100 with auto-normalize)

**Segmentation auto-detect** — string/categorical columns with <20 unique values suggested as segmentation fields.

Output: proposed mapping with confidence scores per field.

### 3. Upload Flow (Two-Step)

**Step 1**: Upload (existing) — save file, generate profile/schema.

**Step 2**: Column Mapping (new) — mapping screen with:
- Pre-filled dropdowns for 4 required fields (from auto-detect)
- Confidence indicators per field
- Optional segmentation field mapping
- Baseline configuration form (min score, max DTI, min income, rate tiers)
- Save blocked until all 4 required fields mapped to distinct columns

**New API endpoints**:
- `GET /api/v1/datasets/{id}/detect-mapping` — run auto-detection
- `PUT /api/v1/datasets/{id}/mapping` — save confirmed mapping + baseline config

Simulation blocked if `column_mapping` is null on the dataset.

### 4. Engine Integration

**No core engine changes.** A thin translation layer renames columns before the engine runs.

New module: `backend/app/simulation/mapper.py`
```python
def apply_column_mapping(df, mapping):
    rename_map = {
        mapping["score_field"]: "bureau_score",
        mapping["income_field"]: "monthly_income",
        mapping["amount_field"]: "desired_amount",
        mapping["dti_field"]: "dti_ratio",
    }
    rename_map = {k: v for k, v in rename_map.items() if k != v}
    return df.rename(columns=rename_map)
```

`baseline.py` and `comparator.py` accept optional config dict with fallback to current hardcoded defaults.

Call chain:
```
simulation_service → load CSV
                   → apply_column_mapping(df, dataset.column_mapping)
                   → run_simulation(mapped_df, rules, dataset.baseline_config)
```

### 5. Rule Extractor Update

LLM prompt in `rule_extractor.py` dynamically includes dataset field names instead of hardcoded list. Rules use **canonical names** (bureau_score, etc.) so they're reusable across datasets.

### 6. File Changes

| File | Change |
|------|--------|
| `models/dataset.py` | Add `column_mapping`, `baseline_config` columns |
| `schemas/dataset.py` | Add mapping/config schemas |
| `services/column_detector.py` | **New** — auto-detection logic |
| `services/dataset_service.py` | Add detect/save mapping functions |
| `simulation/mapper.py` | **New** — column rename function |
| `simulation/baseline.py` | Accept optional config param |
| `simulation/comparator.py` | Accept optional config param |
| `simulation/engine.py` | Pass config through |
| `api/v1/datasets.py` | Add 2 new endpoints |
| `services/simulation_service.py` | Load mapping, apply rename |
| `pipeline/rule_extractor.py` | Dynamic field list |
| `frontend/.../datasets/[id]/page.tsx` | Add mapping UI |
| `frontend/.../datasets/mapping-form.tsx` | **New** — mapping form component |

**New files**: 3 | **Modified files**: 10

### 7. Backward Compatibility

- Existing datasets: `column_mapping = null`, `baseline_config = null` → skip rename, use defaults
- Existing simulations: unchanged, results preserved
- DB migration: adds nullable columns only, no data migration
