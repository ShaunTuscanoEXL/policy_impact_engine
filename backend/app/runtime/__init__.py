"""Runtime evaluation of a Live Rule Repository version against loan
records.

The evaluator is intentionally pure-Python (no DB) so the same code can
serve impact-runs against the loan_records corpus and dry-run scenarios
in the future.
"""
from app.runtime.rule_engine import (
    DecisionResult,
    LoanContext,
    evaluate_snapshot,
)

__all__ = ["DecisionResult", "LoanContext", "evaluate_snapshot"]
