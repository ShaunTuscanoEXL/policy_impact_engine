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
  test_case_suite?: { id: string; total_cases: number } | null;
}
