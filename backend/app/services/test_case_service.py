"""Service layer for test case suite operations."""

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.test_case import TestCaseSuite, TestCase, TestCaseCategory
from app.models.rule import RuleSet, RuleSetStatus
from app.pipeline.rule_compiler import compile_rules
from app.pipeline.test_case_generator import generate_test_cases, TestCaseSuiteOutput, GeneratedTestCase
from app.schemas.rule import RuleDefinition


async def generate_and_save(
    rule_set_id: str,
    rules: list,  # list of Rule ORM objects
    baseline_config: dict | None,
    db: AsyncSession,
) -> TestCaseSuite:
    """Generate test cases from rules and persist to DB.

    Args:
        rule_set_id: The rule set ID
        rules: List of Rule ORM objects from the rule set
        baseline_config: Optional baseline config overrides
        db: Database session

    Returns:
        The persisted TestCaseSuite with test cases
    """
    # Convert DB Rule objects to RuleDefinition schemas
    rule_definitions = []
    for rule in rules:
        rule_definitions.append(
            RuleDefinition(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                description=rule.description or "",
                rule_type=rule.rule_type.value if hasattr(rule.rule_type, 'value') else rule.rule_type,
                conditions=rule.conditions,
                actions=rule.actions,
                priority=rule.priority,
                source_section=rule.source_section or "",
                confidence=rule.confidence,
            )
        )

    # Compile rules
    compiled = compile_rules(rule_definitions)

    # Generate test cases
    output = generate_test_cases(compiled, rule_definitions, baseline_config)

    # Create suite in DB
    suite = TestCaseSuite(
        rule_set_id=uuid.UUID(rule_set_id) if isinstance(rule_set_id, str) else rule_set_id,
        total_cases=output.total_cases,
        cases_by_category=output.cases_by_category,
    )
    db.add(suite)
    await db.flush()
    await db.refresh(suite)

    # Create individual test cases
    for tc in output.test_cases:
        test_case = TestCase(
            suite_id=suite.id,
            test_case_id=tc.test_case_id,
            description=tc.description,
            source_rule_ids=tc.source_rule_ids,
            category=TestCaseCategory(tc.category.value),
            inputs=tc.inputs,
            expected_outcome=tc.expected_outcome,
        )
        db.add(test_case)

    await db.flush()
    return suite


async def get_suite(suite_id: str, db: AsyncSession) -> TestCaseSuite | None:
    """Get a test case suite by ID with all test cases loaded."""
    stmt = (
        select(TestCaseSuite)
        .options(selectinload(TestCaseSuite.test_cases))
        .where(TestCaseSuite.id == uuid.UUID(suite_id))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_rule_set(rule_set_id: str, db: AsyncSession) -> TestCaseSuite | None:
    """Get the most recent test case suite for a rule set."""
    stmt = (
        select(TestCaseSuite)
        .options(selectinload(TestCaseSuite.test_cases))
        .where(TestCaseSuite.rule_set_id == uuid.UUID(rule_set_id))
        .order_by(TestCaseSuite.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_suites(db: AsyncSession) -> list[TestCaseSuite]:
    """List all test case suites (without individual test cases)."""
    stmt = select(TestCaseSuite).order_by(TestCaseSuite.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())
