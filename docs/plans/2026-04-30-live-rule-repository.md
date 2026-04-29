# Live Rule Repository — Architecture & Phased Plan

**Date:** 2026-04-30
**Status:** Approved — Slice 0 in flight
**Owner:** Credit Policy Engineering

## 1. Goals

Today each uploaded BRD produces an isolated rule set. To enable continuous policy
evolution we are introducing a single authoritative **Live Rule Repository** per
(product, jurisdiction) with:

1. Subsystem classification of rules (BUREAU_GATE, DTI_GATE, PRICING_TIER, …)
2. Round-trip Python codegen (export now, import later)
3. Diff + conflict detection when a new BRD lands on the live baseline
4. Human-in-the-loop conflict workbench
5. Impact execution (run any version against the `loan_records` corpus)

## 2. Decisions Locked In

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | One repo per (product, jurisdiction); subsystems for grouping inside | Simpler model; matches how policy actually evolves |
| 2 | `decided_by` username string only — no RBAC yet | Keep slice small; bolt RBAC on later |
| 3 | Codegen export only this slice; Python upload/import deferred | Trust-source assumption when we add it later |
| 4 | Hard conflicts block merge; soft conflicts warn-but-allow | Reviewers act on signal, not noise |
| 5 | Batched impact runs (Celery) | Build for 1M records from day one |
| 6 | One merge = one version | Cleanest audit trail |
| 7 | Hybrid retirement detection: explicit LLM signal + inference fallback | See §6 |

## 3. Target Architecture

```
brd_documents → LLM extract → candidate rule_set
                                    │
                                    ▼
        ┌──────────────────────────────────────┐
        │  Reconciliation: diff vs live repo   │
        │  classify into NEW/DUPLICATE/        │
        │  SUPERSEDE/CONFLICT/RETIRE           │
        └──────────────────────────────────────┘
                                    │
                                    ▼
        ┌──────────────────────────────────────┐
        │  HITL Workbench                       │
        │  accept/reject/edit/                  │
        │  supersede/keep-both                  │
        └──────────────────────────────────────┘
                                    │
                                    ▼ apply
        ┌──────────────────────────────────────┐
        │  Live Rule Repository v+1             │
        │  snapshot + python_export + lineage   │
        └──────────────────────────────────────┘
                  │                   │
        Codegen   │                   │  Impact engine
                  ▼                   ▼
            rules_live.py     ImpactRun(base, candidate)
```

## 4. Data Model

### 4.1 Modified: `Rule`
Add columns:

```python
subsystem: SAEnum(Subsystem)         # BUREAU_GATE, DTI_GATE, ... (see §5)
canonical_key: String(128) indexed   # stable hash for cross-BRD identity
semantic_signature: JSONB            # normalized form for diff
effective_from: DateTime | None
effective_until: DateTime | None
supersedes_rule_id: UUID FK self     # lineage
origin_brd_id: UUID FK               # which BRD introduced/last modified this rule
```

### 4.2 New: `live_rule_repositories`

```python
id: UUID
name: str                # e.g. "US Personal Loan — Production"
product: str             # "PERSONAL"
jurisdiction: str        # "US"
current_version: int     # points at the HEAD version
description: str | None
created_at, updated_at
```

### 4.3 New: `live_rule_versions`

```python
id: UUID
repository_id: FK
version_number: int                # monotonic per repository
parent_version_id: UUID | None     # lineage
source_brd_id: UUID | None         # which BRD produced this version (null = manual / initial)
merge_proposal_id: UUID | None     # link to HITL decision record
summary: str                       # "Added DTI cap tightening (BRD-001), pricing tier expansion (BRD-003)"
rule_snapshot: JSONB               # full materialized rule set at this version
python_export: TEXT                # generated rules.py for this version
created_at: DateTime
created_by: str | None             # username string for now
```

### 4.4 New: `live_rule_entries` (HEAD-only, denormalized for fast reads)

```python
id: UUID
repository_id: FK
rule_id: FK
canonical_key: str
is_active: bool
added_in_version: int
last_modified_in_version: int
```

### 4.5 New: `merge_proposals`

```python
id: UUID
repository_id: FK
base_version: int                  # which version we are diffing against
source_brd_id: FK
status: enum                       # PENDING | APPROVED | REJECTED | APPLIED
decided_by: str | None
decided_at: DateTime | None
created_at: DateTime
```

### 4.6 New: `merge_proposal_items`

```python
id: UUID
proposal_id: FK
category: enum                     # see §6
incoming_rule_id: UUID | None      # candidate
live_rule_id: UUID | None          # existing
diff: JSONB                        # field-level diff
suggested_action: enum             # ACCEPT | REJECT | SUPERSEDE | DROP | KEEP_BOTH | EDIT_NEEDED | RETIRE
user_action: enum | None
user_edits: JSONB | None           # if EDIT_NEEDED: the modified rule body
notes: TEXT | None
severity: enum                     # SOFT | HARD | INFO   ← controls block vs warn
```

### 4.7 New: `impact_runs`

```python
id: UUID
base_version_id: FK
candidate_version_id: FK
loan_record_filter: JSONB          # optional cohort filter
status: enum                       # PENDING | RUNNING | COMPLETED | FAILED
summary: JSONB                     # see below
created_at, completed_at
```

`summary` JSONB shape:

```json
{
  "total_loans": 10000,
  "decision_distribution": {
    "base":      {"APPROVED": 6240, "APPROVED_WITH_CONDITIONS": 1180, "REJECTED": 2580},
    "candidate": {"APPROVED": 5970, "APPROVED_WITH_CONDITIONS": 1310, "REJECTED": 2720}
  },
  "decision_flips": {
    "approved_to_rejected": 320,
    "rejected_to_approved": 50,
    "approved_to_conditional": 130
  },
  "by_subsystem": { "DTI_GATE": {"flips_caused": 280}, "BUREAU_GATE": {"flips_caused": 40} },
  "by_segment": {
    "SUPER_PRIME": {"approval_rate_change": -0.012},
    "PRIME":       {"approval_rate_change": -0.034},
    "NEAR_PRIME":  {"approval_rate_change": -0.087},
    "SUBPRIME":    {"approval_rate_change": -0.142}
  },
  "expected_loss_change_pct": -22.4,
  "portfolio_yield_change_bps": 18
}
```

## 5. Subsystem Taxonomy

```
BUREAU_GATE        # bureau_score, bureau_score_model, bureau_source
INCOME_GATE        # monthly_income, annual_income (floors)
DTI_GATE           # debt_to_income_ratio, dti caps
EMPLOYMENT_GATE    # employment_type, employment_tenure_months
BANKING_BEHAVIOR   # cheque_bounces_6m, salary_credit_consistency_6m,
                   # banking_stability_index, low_balance_instances_6m
PRICING_TIER       # bureau-score → base interest_rate mapping (tiered)
RATE_MODIFIER      # adjustments to interest_rate (premium, discount)
AMOUNT_CAP         # desired_amount / eligible_amount limits
FRAUD_SIGNAL       # fraud signals, AML triggers
REGULATORY_FLOOR   # floors mandated by CFPB/TILA/FCRA/ECOA
EXPOSURE_LIMIT     # active_loans, unsecured_loans, total exposure caps
SCORING_MODEL      # G5/G6 thresholds; internal model gates
```

## 6. Conflict Categories & Default Actions

| Category | Detection | Default | Severity |
|----------|-----------|---------|----------|
| EXACT_DUPLICATE | Same canonical_key + identical thresholds + same actions | DROP | INFO |
| THRESHOLD_TIGHTENING | Same key, stricter threshold | SUPERSEDE | SOFT |
| THRESHOLD_RELAXATION | Same key, looser threshold | SUPERSEDE w/ warning | SOFT |
| OPPOSITE_DIRECTION | Same field, contradictory operator | NEEDS_HUMAN | **HARD** |
| TIERED_REPLACEMENT | Single → tiered set or vice versa | SUPERSEDE_GROUP | SOFT |
| OVERLAPPING_RANGE | Different rules with intersecting ranges on same field | NEEDS_HUMAN | SOFT |
| NEW_RULE | No matching canonical_key | ACCEPT | INFO |
| REMOVED_RULE | Live has rule, BRD retires it | RETIRE | INFO |
| ACTION_DRIFT | Same key/threshold but different action (REJECT → FLAG) | NEEDS_HUMAN | **HARD** |
| COVERAGE_GAP | Tiered group retires but new tiers leave a range uncovered | NEEDS_HUMAN | **HARD** |

**Hard severity** items block "Apply Merge" until resolved.
**Soft severity** items show a warning banner but allow apply.

## 7. Retirement Strategy

### Layer 1 — Explicit LLM signal (preferred)

Extend the rule extractor prompt so the LLM emits `retires_pattern` items when BRD
prose explicitly retires/replaces an existing rule. Signals to look for:

- "previously enforced", "currently set to", "is replaced by"
- "Current State" tables showing old rules being modified
- "no longer enforced", "deprecated", "removed in this revision"
- Tier replacement: a 3-tier table being replaced by a 5-tier one

LLM emits:

```json
{
  "incoming_rules": [...],
  "retirements": [
    {
      "subsystem": "PRICING_TIER",
      "basis": "supersedes_full_table",
      "evidence_section": "Section 4.3 replaces 3-tier structure"
    },
    {
      "canonical_key": "DTI_GATE::dti_ratio::gt",
      "basis": "explicit_replacement"
    }
  ]
}
```

### Layer 2 — Inference fallback

If a live rule's `canonical_key` is NOT mentioned anywhere in the new BRD AND
the BRD's "Current State" section listed it, propose RETIRE with low confidence
and route to HITL with a clear "Inferred retirement?" badge.

Coverage-gap detection runs after retirement: if all rules in a tier group retire
and the new tier set doesn't cover the same range, flag COVERAGE_GAP (HARD).

## 8. Phased Plan

| Phase | Scope | Depends On |
|-------|-------|------------|
| 1 | Subsystem taxonomy + Rule normalization (subsystem, canonical_key) | — |
| 2 | Live Rule Repository tables + snapshots | 1 |
| 3 | Python codegen export | 2 |
| 4 | Diff & conflict engine | 1, 2 |
| 5 | HITL Conflict Workbench UI | 4 |
| 6 | Impact runner (Celery batch) | 2 + existing rule evaluator |

Phase 1 + 2 ship together. Phase 3 ‖ 4. Phase 5 needs 4. Phase 6 follows.

## 9. Slice 0 — Walking Skeleton

**Demo target:** upload BRD → see merge proposal → click apply → see new live
version → download `rules.py`.

Scope:
- Add `subsystem` + `canonical_key` to `Rule` (Phase 1, minimal)
- Add `live_rule_repositories` + `live_rule_versions` + minimal `live_rule_entries` (Phase 2, snapshot-only)
- Build `GET /api/v1/live-repo/{id}/export.py` codegen (Phase 3, write-side)
- Stub merge engine: NEW / DUPLICATE / CONFLICT (3 buckets only)
- Minimal HITL UI: list of items, accept-all / reject-all per category
- Defer impact runner entirely (Phase 6 = next slice)

## 10. Codegen Format (Python export)

```python
# Generated: us_personal_loan_v17.py
"""
LIVE RULE REPOSITORY — US Personal Loan (Production)
Version 17 — generated 2026-04-30 from merge of BRD-PL-2026-001
DO NOT EDIT GENERATED HEADER — manual edits below the marker are preserved.
"""
from policy_engine.runtime import RuleContext, decision

# ─── BUREAU_GATE ─────────────────────────────────────────────
@rule(id="R-BUR-001", subsystem="BUREAU_GATE", priority=100,
      origin="BRD-PL-2026-001", version_added=14)
def fico_minimum(ctx: RuleContext):
    """Minimum FICO bureau score for personal loan eligibility."""
    if ctx.bureau_score < 720:
        return decision.REJECT(reason="SUBPRIME_FICO_SCORE",
                               adverse_action="AAN_FCRA_v2")

# ─── DTI_GATE ────────────────────────────────────────────────
@rule(id="R-DTI-001", subsystem="DTI_GATE", priority=90, ...)
def dti_cap(ctx: RuleContext):
    if ctx.debt_to_income_ratio > 0.35:
        return decision.REJECT(reason="HIGH_DTI_RATIO")

# ... grouped by subsystem in priority order
```

Format chosen so that:
- Every rule is a decorated function — testable, debuggable, lintable
- Subsystem grouping is readable for humans
- AST-parseable round-trip back to JSON in Phase 3b (when import lands)

## 11. API Surface (Slice 0)

| Method | Path | Purpose |
|--------|------|---------|
| GET    | `/api/v1/live-repo` | List repositories |
| POST   | `/api/v1/live-repo` | Create repository (initial setup) |
| GET    | `/api/v1/live-repo/{id}` | Repository detail (incl. current_version) |
| GET    | `/api/v1/live-repo/{id}/versions` | List all versions |
| GET    | `/api/v1/live-repo/{id}/version/{n}` | Version detail (snapshot) |
| GET    | `/api/v1/live-repo/{id}/export.py` | Download generated Python (HEAD) |
| GET    | `/api/v1/live-repo/{id}/version/{n}/export.py` | Historical export |
| POST   | `/api/v1/merge-proposal` | Create proposal from a rule_set vs live |
| GET    | `/api/v1/merge-proposal/{id}` | Proposal detail with all items |
| PATCH  | `/api/v1/merge-proposal/{id}/items/{item_id}` | Set user_action + edits + notes |
| POST   | `/api/v1/merge-proposal/{id}/apply` | Apply approved proposal → new version |

## 12. Open Risks

- **Canonical-key collisions** when two semantically distinct rules share
  `(subsystem, field, operator)` triple — mitigation: include action_type +
  threshold_class in the hash
- **LLM subsystem classification inconsistency** — mitigation: post-validation
  against enum, fallback via field→subsystem lookup table
- **Snapshot table growth** — fine at 100s of versions; may need GIN-indexed
  JSONB or per-version partitioning at 10k+ versions
- **Schema migration risk** — project doesn't use Alembic; for these new
  tables we drop on prod and let `create_all` recreate them. Loan records
  are isolated. Documented in [[Setup/Policy Impact Engine — DB Migration Strategy]]

## 13. Related

- Repo: `C:\Vishnu\Claude\policy_impact_engine`
- Project hub: `Projects/Policy Impact Engine.md` (Obsidian)
- Decision note: `Decisions/Live Rule Repository — Architecture.md` (Obsidian)
- Builds on: US fintech alignment of `seed_loan_records.py` and sample BRDs
  (commits `f3f2def` and `04a5aed`)
