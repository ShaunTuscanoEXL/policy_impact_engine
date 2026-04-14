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

export interface Rule {
  id: string;
  rule_set_id: string;
  rule_id: string;
  rule_name: string;
  description: string;
  rule_type: "ELIGIBILITY" | "PRICING" | "CAP" | "THRESHOLD" | "SCORING";
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
  test_case_suite?: { id: string; total_cases: number } | null;
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
