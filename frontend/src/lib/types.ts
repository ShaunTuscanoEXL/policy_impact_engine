export interface BrdDocument {
  id: string;
  filename: string;
  file_type: string;
  created_at: string;
}

export interface Dataset {
  id: string;
  name: string;
  description: string | null;
  file_type: string;
  row_count: number;
  column_schema: Record<string, any>;
  sample_data: Record<string, any>[];
  data_profile: Record<string, any>;
  column_mapping: Record<string, any> | null;
  baseline_config: Record<string, any> | null;
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

export interface Simulation {
  id: string;
  scenario_name: string;
  dataset_id: string;
  rule_set_id: string;
  dataset_name: string | null;
  rule_set_name: string | null;
  version: number;
  status: "PENDING" | "RUNNING" | "AWAITING_REVIEW" | "COMPLETED" | "FAILED";
  created_at: string;
  completed_at: string | null;
}

export interface SimulationResult {
  id: string;
  simulation_id: string;
  summary_stats: ImpactSummary;
  segment_analysis: Record<string, any>;
  financial_impact: Record<string, any>;
  conflict_report: any;
  created_at: string;
}

export interface ImpactSummary {
  total_customers: number;
  affected_customers: number;
  affected_percentage: number;
  decision_changes: {
    approved_to_rejected: number;
    rejected_to_approved: number;
    unchanged: number;
    baseline_approved: number;
    baseline_rejected: number;
    simulated_approved: number;
    simulated_rejected: number;
  };
  amount_changes: {
    increased: number;
    decreased: number;
    unchanged: number;
    avg_delta: number;
    total_delta: number;
  };
  segment_breakdown: Record<string, any>;
  financial_impact: Record<string, any>;
}

export interface Scenario {
  id: string;
  name: string;
  description: string | null;
  simulation_ids: string[];
  comparison_result: any;
  created_at: string;
}

export interface TestCase {
  id: string;
  test_case_id: string;
  description: string;
  source_rule_ids: string[];
  category: string;
  inputs: Record<string, any>;
  expected_outcome: Record<string, any>;
}

export interface TestCaseSuite {
  id: string;
  rule_set_id: string;
  total_cases: number;
  cases_by_category: Record<string, number>;
  test_cases: TestCase[];
  created_at: string;
}

export interface BrdWorkflow {
  brd_id: string;
  rule_set: { id: string; status: string; rules_count: number } | null;
  simulation: { id: string; status: string; scenario_name: string } | null;
  test_case_suite?: { id: string; total_cases: number } | null;
}

export interface PipelineRunResponse {
  status: string;
  simulation_id: string;
  rule_set_id: string;
  impact_summary: ImpactSummary | null;
  extracted_rules: any[] | null;
  validation_result: any | null;
  rules_extracted: number;
  error: string | null;
}
