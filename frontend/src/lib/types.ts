export interface BrdDocument {
  id: string;
  filename: string;
  file_type: string;
  created_at: string;
  /** Slice D enrichments — let the BRD list show downstream
   *  progression at a glance. */
  rule_set_count?: number;
  total_rules?: number;
  has_merge_proposal?: boolean;
  is_merged_into_repo?: boolean;
  has_test_suite?: boolean;
  has_executed_test_suite?: boolean;
}


export interface RuleSet {
  id: string;
  brd_document_id: string;
  version: number;
  name: string;
  description: string | null;
  status: "DRAFT" | "REVIEWED" | "APPROVED" | "ARCHIVED";
  rules: Rule[];
  created_at: string;
  /** Slice 1 — decision attribution captured on PATCH …/approve */
  approved_by?: string | null;
  approved_at?: string | null;
  approval_notes?: string | null;
}

export type Subsystem =
  | "BUREAU_GATE" | "INCOME_GATE" | "DTI_GATE" | "EMPLOYMENT_GATE"
  | "BANKING_BEHAVIOR" | "PRICING_TIER" | "RATE_MODIFIER" | "AMOUNT_CAP"
  | "FRAUD_SIGNAL" | "REGULATORY_FLOOR" | "EXPOSURE_LIMIT"
  | "SCORING_MODEL" | "UNCLASSIFIED";

export interface Rule {
  id: string;
  rule_set_id: string;
  rule_id: string;
  rule_name: string;
  description: string;
  rule_type: "ELIGIBILITY" | "PRICING" | "CAP" | "THRESHOLD" | "SCORING";
  subsystem?: Subsystem | null;
  canonical_key?: string | null;
  conditions: Condition[];
  actions: Action[];
  priority: number;
  confidence: number;
  source_section: string;
  has_conflicts: boolean;
  conflict_details: any;
  /** Slice 7 — optional governance metadata. */
  policy_intent?: string | null;
  regulatory_citation?: string | null;
}

export interface Condition {
  field: string;
  operator: string;
  value: any;
  logic: string;
  /** Slice 15 — "explicit" = the rule's own condition; "scope" = an
   *  eligibility/scope gate auto-injected from BRD context (flagged +
   *  reviewer-removable). Absent on pre-Slice-15 rules → treat as
   *  explicit. */
  origin?: "explicit" | "scope";
}

export interface Action {
  action_type: "SET" | "REJECT" | "ADJUST" | "FLAG";
  target_field: string;
  value: any;
  description: string;
}


export interface MatchedCustomer {
  id: string;
  loan_application_id: string;
  request_payload: Record<string, any>;
  response_payload: Record<string, any>;
  match_reason: string;
}

export interface MatchedCustomerPage {
  items: MatchedCustomer[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface TestCase {
  id: string;
  test_case_id: string;
  description: string;
  source_rule_ids: string[];
  category: string;
  input_values: Record<string, any>;
  filter_logic: Array<{
    field_name: string;
    json_path: string;
    operator: string;
    value: any;
    description: string;
  }>;
  filter_description: string | null;
  expected_outcome: Record<string, any>;
  rationale: string | null;
  match_count: number;
  matched_customers: MatchedCustomer[];
}

export interface TestCaseSuite {
  id: string;
  rule_set_id: string;
  rule_set_name: string | null;
  total_cases: number;
  cases_by_category: Record<string, number>;
  coverage_stats: Record<string, any>;
  suggested_counts: Record<string, number>;
  test_cases: TestCase[];
  created_at: string;
  last_execution_report?: SuiteExecutionResponse | null;
  last_executed_at?: string | null;
  last_executed_against_version_id?: string | null;
  /** True when the source rule_set has been edited after this suite
   *  was generated. */
  is_stale?: boolean;
  rule_set_last_modified_at?: string | null;
  /** Slice 1 — who ran the latest execution and (optionally) why. */
  last_executed_by?: string | null;
  last_execution_rationale?: string | null;
}

export interface SuggestedCounts {
  positive: number;
  negative: number;
  boundary: number;
  edge: number;
  interaction: number;
  total: number;
  rationale: Record<string, any>;
}

export interface TestCaseSuiteListItem {
  id: string;
  rule_set_id: string;
  rule_set_name: string | null;
  brd_id: string | null;
  brd_filename: string | null;
  total_cases: number;
  cases_by_category: Record<string, number>;
  created_at: string;
  /** Slice D enrichment — inline pass-rate display so the list shows
   *  "X / Y passing vs vN" without forcing a click. */
  last_execution?: SuiteLastExecutionInline | null;
  /** True when the source rule_set has been edited after this suite
   *  was generated — the test cases (and any prior execution) may not
   *  reflect current rules. UI surfaces a STALE badge. */
  is_stale?: boolean;
}

export interface BrdWorkflow {
  brd_id: string;
  rule_set: { id: string; status: string; rules_count: number } | null;
  test_case_suite?: {
    id: string;
    total_cases: number;
    cases_by_category?: Record<string, number>;
    last_execution?: {
      version_id: string | null;
      version_number: number | null;
      executed_at: string | null;
      matches_expected: number;
      deviates_from_expected: number;
      cases_evaluated: number;
    } | null;
  } | null;
  merge_proposal?: {
    id: string;
    status: "PENDING" | "APPROVED" | "REJECTED" | "APPLIED";
    repository_id: string;
    base_version: number;
    summary: string | null;
    decided_by: string | null;
  } | null;
  live_repo_version?: {
    repository_id: string;
    version_number: number;
    version_id: string;
    summary: string | null;
    parent_version_number: number | null;
    parent_version_id: string | null;
  } | null;
  impact_run?: {
    id: string;
    status: ImpactRunStatus;
    base_version_id: string | null;
    candidate_version_id: string;
    summary: ImpactRunSummary | null;
    created_at: string;
  } | null;
}


// ── Live Rule Repository ───────────────────────────────────────────────

export interface LiveRepository {
  id: string;
  name: string;
  product: string;
  jurisdiction: string;
  description: string | null;
  current_version: number;
  /** ID of the version flagged as production-live. May be null on a brand-
   *  new repo before its first promotion. May point at a version BELOW
   *  current_version when a newer candidate is sitting unpromoted. */
  production_version_id?: string | null;
  /** Convenience: integer version number of production_version_id. */
  production_version_number?: number | null;
  production_promoted_at?: string | null;
  production_promoted_by?: string | null;
  /** Slice 1 — free-text justification captured at promotion time. */
  production_promotion_rationale?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PromoteVersionResponse {
  repository_id: string;
  production_version_id: string;
  production_version_number: number;
  promoted_by: string;
  promoted_at: string;
  rationale?: string | null;
}

export interface LiveRepositoryDetail extends LiveRepository {
  versions: LiveVersionSummary[];
}

export interface LiveVersionSummary {
  id: string;
  version_number: number;
  parent_version_id: string | null;
  source_brd_id: string | null;
  merge_proposal_id: string | null;
  summary: string | null;
  rule_count: number;
  created_at: string;
  created_by: string | null;
}

export interface LiveVersionDetail extends LiveVersionSummary {
  rule_snapshot: Array<Record<string, any>>;
}


// ── Merge proposals ────────────────────────────────────────────────────

export type MergeCategory =
  | "EXACT_DUPLICATE" | "THRESHOLD_TIGHTENING" | "THRESHOLD_RELAXATION"
  | "OPPOSITE_DIRECTION" | "TIERED_REPLACEMENT" | "OVERLAPPING_RANGE"
  | "NEW_RULE" | "REMOVED_RULE" | "ACTION_DRIFT" | "COVERAGE_GAP";

export type MergeSeverity = "INFO" | "SOFT" | "HARD";

export type MergeAction =
  | "ACCEPT" | "REJECT" | "SUPERSEDE" | "SUPERSEDE_GROUP"
  | "DROP" | "KEEP_BOTH" | "EDIT_NEEDED" | "RETIRE" | "NEEDS_HUMAN";

/** Full rule details inlined on merge items so the workbench can render
 *  the actual policy (rule name, all conditions, all actions with target+
 *  value) rather than just the canonical 4-field projection in `diff`. */
export interface MergeRulePayload {
  rule_id: string | null;
  rule_name: string | null;
  description: string | null;
  rule_type: string | null;
  subsystem: string | null;
  canonical_key: string | null;
  conditions: Array<Record<string, any>>;
  actions: Array<Record<string, any>>;
  priority: number | null;
  confidence: number | null;
  source_section: string | null;
}

export interface MergeItem {
  id: string;
  category: MergeCategory;
  severity: MergeSeverity;
  canonical_key: string | null;
  incoming_rule_id: string | null;
  live_rule_id: string | null;
  diff: Record<string, any> | null;
  suggested_action: MergeAction;
  user_action: MergeAction | null;
  user_edits: Record<string, any> | null;
  notes: string | null;
  rationale: string | null;
  confidence: number;
  /** Full incoming-side rule (from candidate rule_set). */
  incoming_rule?: MergeRulePayload | null;
  /** Full live-side rule (from current HEAD snapshot). */
  live_rule?: MergeRulePayload | null;
}

export interface MergeProposal {
  id: string;
  repository_id: string;
  base_version: number;
  source_brd_id: string;
  source_rule_set_id: string;
  status: "PENDING" | "APPROVED" | "REJECTED" | "APPLIED";
  summary: string | null;
  decided_by: string | null;
  decided_at: string | null;
  /** Slice 1 — free-text reason captured at apply time. */
  decision_rationale?: string | null;
  created_at: string;
  items: MergeItem[];
  counts_by_category: Record<string, number>;
  counts_by_severity: Record<string, number>;
  blockers: string[];
}

export interface MergeApplyResult {
  applied: boolean;
  new_version_number: number | null;
  new_version_id: string | null;
  blockers: string[];
  summary: string | null;
}


// ── Impact runs ────────────────────────────────────────────────────────

export type ImpactRunStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";

export interface ImpactRun {
  id: string;
  repository_id: string;
  base_version_id: string | null;
  candidate_version_id: string;
  status: ImpactRunStatus;
  summary: ImpactRunSummary | null;
  error: string | null;
  created_at: string;
  completed_at: string | null;
  created_by: string | null;
  /** Slice 1 — optional "why we kicked off this run". */
  rationale?: string | null;
}

export interface ImpactRunSummary {
  total_loans: number;
  decision_distribution: {
    base: Record<string, number>;
    candidate: Record<string, number>;
  };
  decision_flips: Record<string, number>;
  by_subsystem: Record<string, { flips_caused: number }>;
  by_segment: Record<string, {
    loans: number;
    base_approval_rate: number;
    candidate_approval_rate: number;
    approval_rate_change: number;
    /** Slice 2 — per-segment USD exposure totals + signed delta. */
    base_funded_amount_usd?: number;
    candidate_funded_amount_usd?: number;
    funded_amount_delta_usd?: number;
  }>;
  /** Slice 2 — plain-English roll-up consumed by the BusinessImpactCard. */
  business_summary?: BusinessImpactSummary;
  /** Slice 13 — offer-term modifications (SET/ADJUST on non-decision
   *  fields like eligible_amount, interest_rate, max_tenure_months).
   *  Lets pricing-only BRDs show meaningful impact even when
   *  decision_flips is zero. */
  offer_modifications?: OfferModifications;
}

export interface OfferModifications {
  loans_with_any_offer_change: number;
  loans_with_offer_change_but_decision_unchanged: number;
  new_writes_by_field: Array<{
    field: string;
    field_class: string;
    loans_affected: number;
  }>;
  new_writes_by_class: Array<{ class: string; loans_affected: number }>;
  dropped_writes_by_field: Array<{
    field: string;
    field_class: string;
    loans_affected: number;
  }>;
  fields_touched_only_in_candidate: string[];
}

/** Plain-English summary block used by the BusinessImpactCard. Every
 *  field is computed server-side from the same loan corpus that drives
 *  the developer-view distribution + flip stats. */
export interface BusinessImpactSummary {
  base_approval_rate: number;
  candidate_approval_rate: number;
  approval_rate_delta: number;
  loans_newly_denied: number;
  loans_newly_approved: number;
  net_funded_loans_change: number;
  base_funded_amount_usd: number;
  candidate_funded_amount_usd: number;
  exposure_change_loss_usd: number;
  exposure_change_gain_usd: number;
  net_exposure_change_usd: number;
  /** Segment with the biggest absolute approval-rate swing; null when
   *  the corpus is empty. UI uses this for the hero callout. */
  top_changed_segment: string | null;
}


// ── Test suite execution report ────────────────────────────────────────

export interface TestCaseExecutionReport {
  test_case_id: string;
  category: string;
  expected_decision: string;
  /** The token actually compared against per-loan. For NEG/BND it's
   *  NOT_TRIGGERED, for POSITIVE it's RULE_FIRED, for INTERACTION it's
   *  ALL_TRIGGERED, otherwise it's the engine decision verbatim. */
  target_outcome?: string;
  matched_loan_count: number;
  /** Distribution in the assertion vocabulary
   *  (RULE_FIRED / NOT_TRIGGERED / engine decision). */
  actual_distribution: Record<string, number>;
  /** Distribution of the engine's actual final decision per loan —
   *  useful when the assertion vocabulary hides what really happened
   *  (e.g. POSITIVE test passes because the source rule fired, but the
   *  engine still REJECTED because another terminal rule overrode it). */
  engine_decision_distribution?: Record<string, number>;
  matches_expected: number;
  /** POSITIVE / BND-fires test where the source rule didn't fire but
   *  the engine still produced the expected decision via another rule
   *  (typical "shadowed by an earlier REJECT" case in gate-style
   *  underwriting). Counted as a soft pass. */
  shadowed?: number;
  deviates_from_expected: number;
  first_deviation_reason: string | null;
}

export interface SuiteExecutionResponse {
  suite_id: string;
  version_id: string;
  version_number: number;
  total_cases: number;
  cases_evaluated: number;
  results: TestCaseExecutionReport[];
  summary: {
    matches_expected: number;
    deviates_from_expected: number;
    by_category: Record<string, { matches: number; deviates: number }>;
  };
}

export interface LoanRecord {
  id: string;
  loan_application_id: string;
  request_payload: Record<string, any>;
  response_payload: Record<string, any>;
  created_at: string;
}

export interface LoanRecordListItem {
  id: string;
  loan_application_id: string;
  decision_status: string | null;
  bureau_score: number | null;
  monthly_income: number | null;
  desired_amount: number | null;
  created_at: string;
}

export interface SuiteLastExecutionInline {
  executed_at: string;
  version_number: number | null;
  total_assertions: number;
  passing: number;
  failing: number;
  pass_rate: number;
}


export interface LoanRecordStats {
  total_records: number;
  decision_distribution: Record<string, number>;
  bureau_score_range: { min: number; max: number; avg: number };
  income_range: { min: number; max: number; avg: number };
}


// ── Dashboard payload (enriched in Slice B) ────────────────────────────

export interface DashboardLiveRepoSummary {
  id: string;
  name: string;
  product: string;
  jurisdiction: string;
  current_version: number;
  production_version_number: number | null;
  has_unpromoted_candidate: boolean;
  updated_at: string | null;
}

export interface DashboardPendingMergeQueue {
  count: number;
  oldest_age_hours: number | null;
  oldest_id: string | null;
}

export interface DashboardLastImpactRun {
  id: string;
  repository_id: string;
  completed_at: string | null;
  total_loans: number;
  total_flips: number;
  flip_rate: number;
  decision_distribution: {
    base: Record<string, number>;
    candidate: Record<string, number>;
  } | null;
  by_subsystem_top: Array<{ key: string; value: number }>;
}

export interface DashboardLastSuiteExecution {
  suite_id: string;
  executed_at: string | null;
  total_assertions: number;
  passing: number;
  failing: number;
  pass_rate: number;
  version_number: number | null;
}

export interface DashboardPipelineCounters {
  brds_uploaded: number;
  rules_extracted: number;
  rule_sets: number;
  merge_proposals: number;
  live_versions: number;
  impact_runs: number;
  test_executions: number;
}

export interface DashboardStats {
  /** Backward-compat fields (kept so existing StatsCards still render) */
  total_brds: number;
  total_loan_records: number;
  total_test_suites: number;
  /** Slice B additions */
  total_repositories: number;
  total_versions: number;
  total_impact_runs: number;
  pipeline: DashboardPipelineCounters;
  pending_merge_queue: DashboardPendingMergeQueue;
  live_repos: DashboardLiveRepoSummary[];
  last_impact_run: DashboardLastImpactRun | null;
  last_suite_execution: DashboardLastSuiteExecution | null;
}

export interface DashboardActivityEvent {
  type:
    | "brd_uploaded"
    | "version_created"
    | "version_promoted"
    | "merge_proposal"
    | "impact_run"
    | "suite_executed";
  ts: string | null;
  title: string;
  subtitle: string;
  href: string;
  accent: "blue" | "amber" | "emerald" | "violet" | "rose" | "fuchsia" | "slate";
}

export interface DashboardTrends {
  approval_rate_history: Array<{
    completed_at: string | null;
    approval_rate: number;
    /** Slice 11 follow-up: per-run flagged + rejected rates so the
     *  trend chart can render all three lines (and a 0% approval
     *  rate doesn't look like flat zero — the FLAGGED line shows
     *  where those loans actually went). */
    flagged_rate?: number;
    rejected_rate?: number;
    total_loans: number;
    run_id: string;
  }>;
  rule_count_history: Array<{
    created_at: string | null;
    repository: string;
    version_number: number;
    rule_count: number;
  }>;
}


// ── Audit timeline ─────────────────────────────────────────────────────

export type AuditAction =
  | "BRD_UPLOADED" | "RULES_EXTRACTED"
  | "RULE_SET_APPROVED" | "RULE_EDITED" | "RULE_DELETED" | "RULE_ADDED"
  | "MERGE_PROPOSAL_CREATED" | "MERGE_PROPOSAL_APPLIED"
  | "MERGE_PROPOSAL_REJECTED" | "MERGE_ITEM_DECIDED" | "VERSION_PROMOTED"
  | "IMPACT_RUN_STARTED" | "IMPACT_RUN_COMPLETED"
  | "SUITE_GENERATED" | "SUITE_EXECUTED";

export type AuditEntityType =
  | "BRD" | "RULE_SET" | "RULE" | "MERGE_PROPOSAL"
  | "LIVE_REPO" | "LIVE_VERSION" | "IMPACT_RUN" | "TEST_SUITE";

export interface AuditEvent {
  id: string;
  action: AuditAction;
  entity_type: AuditEntityType;
  entity_id: string;
  actor: string;
  rationale: string | null;
  brd_id: string | null;
  repository_id: string | null;
  metadata?: Record<string, any> | null;
  created_at: string;
}


// ── Slice 14: BRD coherence report ─────────────────────────────────────

export type CoherenceIssueKind =
  | "dead_consumer"
  | "orphan_producer"
  | "unreferenced_eligibility"
  | "dependency_cycle";

export interface CoherenceIssue {
  kind: CoherenceIssueKind;
  severity: "error" | "warning" | "info";
  rule_ids: string[];
  field: string | null;
  message: string;
}

export interface CoherenceReport {
  is_coherent: boolean;
  issue_count: number;
  error_count: number;
  warning_count: number;
  issues: CoherenceIssue[];
  produced_fields: string[];
  consumed_fields: string[];
  /** [producer_rule_id, consumer_rule_id, field] triples. */
  dependency_edges: string[][];
}


// ── Slice 10: production drift watch ───────────────────────────────────

export interface DriftDecisionDelta {
  predicted_pct: number;
  observed_pct: number;
  delta_pct: number;
  predicted_count: number;
  observed_count: number;
}

export interface DriftSegmentDelta {
  loans: number;
  predicted_approval_rate: number;
  observed_approval_rate: number;
  approval_rate_delta: number;
  observed_funded_amount_usd: number;
}

export interface DriftReport {
  repository_id: string;
  production_version_id: string;
  production_version_number: number;
  computed_at: string;
  predicted_source: {
    impact_run_id: string;
    completed_at: string | null;
    loan_count: number | null;
  } | null;
  observed: {
    loan_count: number;
    decision_distribution: Record<string, number>;
    by_segment: Record<string, Record<string, number | string>>;
  };
  drift: {
    decision_distribution: Record<string, DriftDecisionDelta>;
    by_segment: Record<string, DriftSegmentDelta>;
    max_abs_delta_pct: number;
    top_drifting_segment: string | null;
  };
  warnings: string[];
}
