export interface BrdDocument {
  id: string;
  filename: string;
  file_type: string;
  created_at: string;
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
}

export interface BrdWorkflow {
  brd_id: string;
  rule_set: { id: string; status: string; rules_count: number } | null;
  test_case_suite?: { id: string; total_cases: number; cases_by_category?: Record<string, number> } | null;
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
  created_at: string;
  updated_at: string;
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
  matched_loan_count: number;
  actual_distribution: Record<string, number>;
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

export interface LoanRecordStats {
  total_records: number;
  decision_distribution: Record<string, number>;
  bureau_score_range: { min: number; max: number; avg: number };
  income_range: { min: number; max: number; avg: number };
}
