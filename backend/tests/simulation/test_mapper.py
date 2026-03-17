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
