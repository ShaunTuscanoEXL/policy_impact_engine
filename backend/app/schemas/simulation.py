from pydantic import BaseModel


class SimulationCreateRequest(BaseModel):
    scenario_name: str
    dataset_id: str
    rule_set_id: str
    parameters: dict | None = None


class SimulationResponse(BaseModel):
    id: str
    scenario_name: str
    dataset_id: str
    rule_set_id: str
    dataset_name: str | None = None
    rule_set_name: str | None = None
    version: int
    status: str
    created_at: str
    completed_at: str | None

    model_config = {"from_attributes": True}


class ImpactSummary(BaseModel):
    total_customers: int
    affected_customers: int
    affected_percentage: float
    decision_changes: dict
    amount_changes: dict
    segment_breakdown: dict
    financial_impact: dict


class SimulationResultResponse(BaseModel):
    id: str
    simulation_id: str
    summary_stats: dict
    segment_analysis: dict | None
    financial_impact: dict | None
    conflict_report: dict | None
    created_at: str

    model_config = {"from_attributes": True}


class ScenarioCreateRequest(BaseModel):
    name: str
    description: str | None = None
    simulation_ids: list[str]


class ScenarioResponse(BaseModel):
    id: str
    name: str
    description: str | None
    simulation_ids: list[str]
    comparison_result: dict | None
    created_at: str

    model_config = {"from_attributes": True}
