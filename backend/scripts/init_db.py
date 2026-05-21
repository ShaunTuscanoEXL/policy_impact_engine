"""Idempotent database bootstrap — create every table + apply additive
migrations, exactly the way the FastAPI app does on startup.

Setup scripts call this BEFORE seeding so the loan_records table (and
every other table, including audit_events and all Slice 1/7 columns)
exists before `seed_loan_records` runs.

It deliberately reuses the app's own ``_apply_additive_migrations`` so
the migration list never drifts from what the running app applies. On
a brand-new database, ``create_all`` creates every table with its
current columns and the ALTER statements are harmless no-ops; on an
existing database the ALTERs backfill the columns added in later
slices.

Usage (from the backend/ directory):
    python -m scripts.init_db
"""
from __future__ import annotations

import asyncio


async def init() -> None:
    # Import the package so Base.metadata is fully populated with every
    # model (BRD, Rule, TestCase, LoanRecord, LiveRepo, Merge, Impact,
    # AuditEvent) before create_all runs.
    import app.models  # noqa: F401  — registers all ORM models
    from app.database import Base, engine
    from app.main import _apply_additive_migrations

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _apply_additive_migrations(conn)
    await engine.dispose()
    print("Database schema created + additive migrations applied.")
    print("Tables include: brd_documents, rule_sets, rules, test_case_suites,")
    print("test_cases, loan_records, live_rule_repositories, live_rule_versions,")
    print("live_rule_entries, merge_proposals, merge_proposal_items, impact_runs,")
    print("audit_events.")


if __name__ == "__main__":
    asyncio.run(init())
