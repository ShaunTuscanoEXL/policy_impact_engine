import pytest
from app.services.field_registry import (
    resolve_field_path,
    json_path_to_sql,
    auto_discover_fields,
    get_all_fields,
)


class TestResolveFieldPath:
    def test_exact_match(self):
        assert resolve_field_path("bureau_score") == "borrower_credit_model.bureau_credits.bureau_score"

    def test_alias_match(self):
        assert resolve_field_path("cibil_score") == "borrower_credit_model.bureau_credits.bureau_score"
        assert resolve_field_path("dti") == "calculated_attributes.debt_to_income_ratio"
        assert resolve_field_path("income") == "borrower_credit_model.customer_inputs.monthly_income"

    def test_normalized_match(self):
        assert resolve_field_path("Bureau Score") == "borrower_credit_model.bureau_credits.bureau_score"
        assert resolve_field_path("MONTHLY_INCOME") == "borrower_credit_model.customer_inputs.monthly_income"

    def test_unknown_field(self):
        assert resolve_field_path("nonexistent_field") is None

    def test_top_level_field(self):
        assert resolve_field_path("desired_amount") == "desired_amount"

    def test_nested_score(self):
        assert resolve_field_path("g5_score") == "calculated_attributes.scores.g5.score"


class TestJsonPathToSql:
    def test_single_level(self):
        result = json_path_to_sql("desired_amount")
        assert result == "request_payload->>'desired_amount'"

    def test_two_levels(self):
        result = json_path_to_sql("decision_context.risk_segment")
        assert result == "request_payload->'decision_context'->>'risk_segment'"

    def test_three_levels(self):
        result = json_path_to_sql("borrower_credit_model.bureau_credits.bureau_score")
        assert result == "request_payload->'borrower_credit_model'->'bureau_credits'->>'bureau_score'"

    def test_deep_nesting(self):
        result = json_path_to_sql("calculated_attributes.scores.g5.score")
        assert result == "request_payload->'calculated_attributes'->'scores'->'g5'->>'score'"


class TestAutoDiscoverFields:
    def test_discovers_leaf_fields(self):
        payload = {
            "new_field": 42,
            "nested": {
                "another_new": "value",
                "deeper": {
                    "deep_field": 100,
                }
            }
        }
        discovered = auto_discover_fields(payload)
        assert "new_field" in discovered
        assert discovered["new_field"] == "new_field"
        assert "another_new" in discovered
        assert discovered["another_new"] == "nested.another_new"
        assert "deep_field" in discovered
        assert discovered["deep_field"] == "nested.deeper.deep_field"

    def test_skips_known_fields(self):
        payload = {"bureau_score": 748}  # Already in registry
        discovered = auto_discover_fields(payload)
        assert "bureau_score" not in discovered

    def test_empty_payload(self):
        discovered = auto_discover_fields({})
        assert discovered == {}


class TestGetAllFields:
    def test_returns_dict(self):
        fields = get_all_fields()
        assert isinstance(fields, dict)
        assert "bureau_score" in fields
        assert len(fields) > 40  # We have many fields registered
