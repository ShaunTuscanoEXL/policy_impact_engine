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
        if not pd.api.types.is_numeric_dtype(df[col]):
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
