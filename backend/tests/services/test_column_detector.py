import pandas as pd
import pytest
from app.services.column_detector import detect_mapping


def test_detect_exact_column_names():
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
    df = pd.DataFrame({
        "bureau_score": [750, 680],
        "monthly_income": [50000, 30000],
        "desired_amount": [500000, 200000],
        "dti_ratio": [0.3, 0.45],
        "region": ["North", "South"],
        "product_type": ["Home Loan", "Personal Loan"],
        "applicant_id": ["APP-0001", "APP-0002"],
    })
    result = detect_mapping(df)
    seg = result.get("segmentation_fields", {})
    assert "region" in seg or "product_type" in seg


def test_detect_dti_auto_normalize():
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
