from pydantic import BaseModel, Field


class BudgetCategory(BaseModel):
    category: str
    estimated_cost: float
    assumption: str


class BudgetAnalysis(BaseModel):
    currency: str
    shoot_days: int
    categories: list[BudgetCategory] = Field(default_factory=list)
    total_estimated_cost: float
    major_cost_drivers: list[str] = Field(default_factory=list)
    budget_risks: list[str] = Field(default_factory=list)