from pydantic import BaseModel, Field


class ResourceRecommendation(BaseModel):
    resource_type: str
    recommendation: str
    source_url: str | None = None
    evidence: str = ""
    estimated_cost: str | None = None


class BudgetAdjustment(BaseModel):
    category: str
    current_estimate: float
    recommended_estimate: float
    reason: str


class ProductionPlan(BaseModel):
    title: str

    overall_strategy: str

    location_strategy: list[str] = Field(
        default_factory=list
    )

    equipment_strategy: list[str] = Field(
        default_factory=list
    )

    vfx_strategy: list[str] = Field(
        default_factory=list
    )

    resource_recommendations: list[
        ResourceRecommendation
    ] = Field(default_factory=list)

    budget_adjustments: list[
        BudgetAdjustment
    ] = Field(default_factory=list)

    production_risks: list[str] = Field(
        default_factory=list
    )

    mitigation_strategies: list[str] = Field(
        default_factory=list
    )

    recommended_shoot_days: int

    confidence: str