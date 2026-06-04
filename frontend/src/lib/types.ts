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
}

export interface Condition {
  field: string;
  operator: string;
  value: any;
  logic: string;
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
  matched_loan_ids: string[];
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
  created_at: string;
  updated_at: string;
}

export interface PromoteVersionResponse {
  repository_id: string;
  production_version_id: string;
  production_version_number: number;
  promoted_by: string;
  promoted_at: string;
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
  }>;
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
