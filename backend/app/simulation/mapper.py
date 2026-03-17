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
