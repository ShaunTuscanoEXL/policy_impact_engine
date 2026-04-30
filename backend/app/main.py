from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.api.v1.brds import router as brds_router
from app.api.v1.rules import router as rules_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.test_cases import router as test_cases_router
from app.api.v1.loan_records import router as loan_records_router
from app.api.v1.live_repo import router as live_repo_router
from app.api.v1.merge import router as merge_router
from app.api.v1.impact import router as impact_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    import app.models.brd
    import app.models.rule
    import app.models.test_case
    import app.models.loan_record
    import app.models.live_repo  # registers LiveRuleRepository / Version / Entry
    import app.models.merge      # registers MergeProposal / MergeProposalItem
    import app.models.impact     # registers ImpactRun
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Additive auto-migrations — new columns added in later slices that
        # create_all() won't apply to a pre-existing table. Idempotent on
        # both Postgres (IF NOT EXISTS) and other dialects (catch + ignore).
        await _apply_additive_migrations(conn)

    # Backfill: for repos that existed before slice A landed,
    # set production_version_id := highest version's id so the UI
    # has something to render. Idempotent.
    from app.database import async_session
    from app.services.live_repo_service import backfill_production_versions
    async with async_session() as db:
        try:
            await backfill_production_versions(db)
        except Exception:
            # Backfill should never block startup
            pass

    # Backfill source_rule_uuids on legacy test cases so existing
    # suites can be re-executed without ambiguity. Idempotent — only
    # touches rows where source_rule_uuids is NULL.
    async with async_session() as db:
        try:
            await _backfill_test_case_uuids(db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "Test-case UUID backfill skipped: %s", e
            )

    # Backfill: split collapsed tiered rules in existing rule_sets that
    # haven't been merged yet. Idempotent — already-split rules pass
    # through unchanged.
    async with async_session() as db:
        try:
            await _backfill_split_tier_rules(db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "Tier-rule split backfill skipped: %s", e
            )

    # Backfill: any rule missing canonical_key / subsystem (e.g. created
    # before the classification step ran, or by a previous version of
    # the tier-split backfill that hardcoded UNCLASSIFIED) gets the
    # proper classification + key now. Idempotent.
    async with async_session() as db:
        try:
            await _backfill_rule_canonical_keys(db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "Canonical-key backfill skipped: %s", e
            )
    yield


async def _backfill_rule_canonical_keys(db) -> None:
    """Walk every Rule with NULL canonical_key OR with subsystem
    UNCLASSIFIED that *should* be classifiable, and populate the
    classification + canonical_key + semantic_signature. Idempotent —
    rules with valid keys are left alone."""
    from sqlalchemy import select
    from app.models.rule import Rule, Subsystem, RuleType
    from app.services.canonical_key import (
        make_canonical_key,
        make_semantic_signature,
    )
    from app.services.rule_classifier import classify as classify_subsystem

    # Also refresh rules whose canonical_key contains the legacy
    # "unknown_field::UNK" placeholder — those were generated before
    # the unconditional-rule fix landed and now have meaningful keys
    # available via the action's target_field.
    rows_q = await db.execute(
        select(Rule).where(
            (Rule.canonical_key.is_(None))
            | (Rule.canonical_key == "")
            | (Rule.canonical_key.like("%unknown_field%"))
            | (Rule.canonical_key.like("%::UNK::%"))
        )
    )
    rules = list(rows_q.scalars())
    if not rules:
        return

    updated = 0
    for r in rules:
        conds = r.conditions if isinstance(r.conditions, list) else []
        acts = r.actions if isinstance(r.actions, list) else []
        try:
            new_sub = classify_subsystem(
                conds,
                acts,
                r.rule_type if isinstance(r.rule_type, RuleType) else RuleType(r.rule_type),
            )
            new_ck = make_canonical_key(new_sub, conds, acts)
            new_sig = make_semantic_signature(conds, acts)
        except Exception:
            continue
        # Only overwrite if the new key is actually better than the old
        # one (i.e. doesn't still contain unknown_field). Prevents
        # accidentally clobbering a hand-curated key.
        if new_ck and "unknown_field" not in new_ck:
            r.canonical_key = new_ck
            r.semantic_signature = new_sig
            if r.subsystem == Subsystem.UNCLASSIFIED:
                r.subsystem = new_sub
            updated += 1
    if updated:
        await db.commit()
        import logging
        logging.getLogger(__name__).info(
            "Backfilled canonical_key + subsystem on %d rule(s).", updated
        )


async def _backfill_split_tier_rules(db) -> None:
    """One-off: legacy rule_sets may have rules where the LLM collapsed
    a tiered table (e.g. four interest-rate bands) into a single rule
    with N OR'd conditions and N actions. Walk all DRAFT rule_sets and
    apply the same _fan_out_tiers logic the live extraction pipeline now
    uses, persisting the split as new Rule rows with subsystem +
    canonical_key + semantic_signature properly populated.

    APPROVED rule_sets are left alone — they've already been reviewed
    and may have been merged into the live repo; re-splitting them would
    require a coordinated re-merge."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.rule import RuleSet, Rule, RuleSetStatus, RuleType, Subsystem
    from app.pipeline.rule_extractor import _fan_out_tiers
    from app.schemas.rule import (
        Action as ActionSchema,
        Condition as ConditionSchema,
        RuleDefinition,
    )
    from app.services.canonical_key import (
        make_canonical_key,
        make_semantic_signature,
    )
    from app.services.rule_classifier import classify as classify_subsystem

    rule_sets_q = await db.execute(
        select(RuleSet)
        .options(selectinload(RuleSet.rules))
        .where(RuleSet.status == RuleSetStatus.DRAFT)
    )
    rule_sets = list(rule_sets_q.scalars())
    if not rule_sets:
        return

    total_added = 0
    total_split = 0
    for rs in rule_sets:
        # Build RuleDefinition objects from DB rows so we can run the
        # same fan-out logic the extractor uses.
        defs: list[RuleDefinition] = []
        original_uuid_by_rule_id: dict[str, str] = {}
        for r in rs.rules:
            try:
                conds = [
                    ConditionSchema(**c) if isinstance(c, dict) else c
                    for c in (r.conditions or [])
                ]
                acts = [
                    ActionSchema(**a) if isinstance(a, dict) else a
                    for a in (r.actions or [])
                ]
                defs.append(
                    RuleDefinition(
                        rule_id=r.rule_id,
                        rule_name=r.rule_name,
                        description=r.description or "",
                        rule_type=r.rule_type.value if hasattr(r.rule_type, "value") else r.rule_type,
                        conditions=conds,
                        actions=acts,
                        priority=r.priority,
                    )
                )
                original_uuid_by_rule_id[r.rule_id] = str(r.id)
            except Exception:
                # If a rule can't be parsed, leave it alone
                continue

        before = len(defs)
        after_defs = _fan_out_tiers(defs)
        after = len(after_defs)

        if after == before:
            continue  # Nothing to do for this rule_set

        # Identify which original rules were split — they're the ones
        # whose rule_id no longer appears in the after list (because
        # _fan_out_tiers gives them suffixes like "RULE-002-T1").
        before_ids = {d.rule_id for d in defs}
        after_ids = {d.rule_id for d in after_defs}
        replaced_original_ids = before_ids - after_ids

        if not replaced_original_ids:
            continue

        # Delete the originals that got split, add the new tier rows.
        # Also nuke any merge_proposal_items that point at the rule,
        # since those proposals were generated against the malformed
        # collapsed rule and are stale once the rule is split. The
        # user can re-trigger propose-from-brd to get fresh proposals.
        from sqlalchemy import delete as sql_delete, text as sql_text
        for rid in replaced_original_ids:
            uuid_str = original_uuid_by_rule_id.get(rid)
            if uuid_str:
                import uuid as _u
                ru = _u.UUID(uuid_str)
                # Drop referencing merge_proposal_items first
                try:
                    await db.execute(
                        sql_text(
                            "DELETE FROM merge_proposal_items "
                            "WHERE incoming_rule_id = :rid"
                        ),
                        {"rid": ru},
                    )
                except Exception:
                    # Table or column may not exist on fresh DBs
                    pass
                await db.execute(
                    sql_delete(Rule).where(Rule.id == ru)
                )
        for d in after_defs:
            if d.rule_id in before_ids:
                continue  # Existing rule, untouched
            cond_dicts = [c.model_dump() for c in d.conditions]
            act_dicts = [a.model_dump() for a in d.actions]
            # Properly classify the new tier rule + compute its keys so
            # the merge engine can reason about it. Without this, split
            # rules show up with empty canonical_key and UNCLASSIFIED
            # subsystem, breaking diff/pairing.
            sub = classify_subsystem(
                cond_dicts,
                act_dicts,
                RuleType(d.rule_type.value if hasattr(d.rule_type, "value") else d.rule_type),
            )
            ck = make_canonical_key(sub, cond_dicts, act_dicts)
            sig = make_semantic_signature(cond_dicts, act_dicts)
            db.add(Rule(
                rule_set_id=rs.id,
                rule_id=d.rule_id,
                rule_name=d.rule_name,
                description=d.description,
                rule_type=RuleType(d.rule_type.value if hasattr(d.rule_type, "value") else d.rule_type),
                conditions=cond_dicts,
                actions=act_dicts,
                priority=d.priority,
                confidence=d.confidence,
                source_section=d.source_section,
                subsystem=sub,
                canonical_key=ck,
                semantic_signature=sig,
            ))
        total_split += len(replaced_original_ids)
        total_added += after - before

    if total_split:
        await db.commit()
        import logging
        logging.getLogger(__name__).info(
            "Split %d collapsed tier rule(s) into %d additional rules.",
            total_split,
            total_added,
        )

    # Any PENDING merge proposal whose source_rule_set was modified by
    # the split is now stale (its items reference rule UUIDs that no
    # longer exist). Regenerate them from a fresh diff so the workbench
    # shows all current rules.
    from sqlalchemy import select
    from app.models.merge import MergeProposal, MergeProposalStatus
    from app.services.live_repo_service import regenerate_proposal_items
    pending_q = await db.execute(
        select(MergeProposal)
        .where(MergeProposal.status == MergeProposalStatus.PENDING)
    )
    refreshed = 0
    for p in pending_q.scalars():
        try:
            await regenerate_proposal_items(db, proposal_id=p.id)
            refreshed += 1
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "Failed to refresh proposal %s: %s", p.id, e
            )
    if refreshed:
        import logging
        logging.getLogger(__name__).info(
            "Refreshed %d PENDING merge proposal(s) after rule-split backfill.",
            refreshed,
        )


async def _backfill_test_case_uuids(db) -> None:
    """One-off: existing test cases were stored before the source-rule
    UUID column existed. Look each one up via its suite's rule_set to
    fill in the UUID(s) so re-execution can disambiguate rule_id
    collisions across BRDs."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.test_case import TestCase, TestCaseSuite
    from app.models.rule import RuleSet
    rows_q = await db.execute(
        select(TestCase)
        .options(
            selectinload(TestCase.suite)
            .selectinload(TestCaseSuite.rule_set)
            .selectinload(RuleSet.rules)
        )
        .where(TestCase.source_rule_uuids.is_(None))
    )
    rows = list(rows_q.scalars())
    if not rows:
        return
    updated = 0
    for tc in rows:
        rule_set = tc.suite.rule_set if tc.suite else None
        if not rule_set or not rule_set.rules:
            continue
        wanted = set(tc.source_rule_ids or [])
        if not wanted:
            continue
        # Within a rule_set, rule_id IS unique — so this lookup is
        # collision-free. The collision only happens once rules from
        # multiple BRDs land in the same live snapshot.
        uuids = [str(r.id) for r in rule_set.rules if r.rule_id in wanted]
        if uuids:
            tc.source_rule_uuids = uuids
            updated += 1
    if updated:
        await db.commit()
        import logging
        logging.getLogger(__name__).info(
            "Backfilled source_rule_uuids on %d test case(s).", updated
        )


async def _apply_additive_migrations(conn) -> None:
    """Run idempotent ALTER TABLE statements for columns introduced after
    the table was first created. Each statement is wrapped so a failure
    on one doesn't block the rest. Postgres-aware via IF NOT EXISTS;
    falls back gracefully on other dialects."""
    from sqlalchemy import text
    statements = [
        # Slice A: production version pointer
        "ALTER TABLE live_rule_repositories "
        "ADD COLUMN IF NOT EXISTS production_version_id UUID NULL",
        "ALTER TABLE live_rule_repositories "
        "ADD COLUMN IF NOT EXISTS production_promoted_at TIMESTAMP NULL",
        "ALTER TABLE live_rule_repositories "
        "ADD COLUMN IF NOT EXISTS production_promoted_by VARCHAR(128) NULL",
        # Slice — rule_id collision fix: store globally-unique UUIDs of
        # the source rule(s) so the executor can disambiguate rules that
        # share a human-readable rule_id (e.g. multiple BRDs both having
        # RULE-001 merged into one live repo).
        "ALTER TABLE test_cases "
        "ADD COLUMN IF NOT EXISTS source_rule_uuids JSON NULL",
    ]
    for stmt in statements:
        try:
            await conn.execute(text(stmt))
        except Exception as e:
            # Log + continue; create_all() above already handles fresh DBs.
            import logging
            logging.getLogger(__name__).warning(
                "Additive migration skipped (%s): %s", stmt[:60], e
            )

app = FastAPI(title="Policy Impact Engine", version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(brds_router, prefix="/api/v1")
app.include_router(rules_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(test_cases_router, prefix="/api/v1")
app.include_router(loan_records_router, prefix="/api/v1")
app.include_router(live_repo_router, prefix="/api/v1")
app.include_router(merge_router, prefix="/api/v1")
app.include_router(impact_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
