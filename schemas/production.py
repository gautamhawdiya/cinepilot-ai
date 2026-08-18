from pydantic import BaseModel

from schemas.screenplay import ScreenplayAnalysis
from schemas.budget import BudgetAnalysis
from schemas.parallel import ParallelResearch



class ProductionState(BaseModel):
    screenplay_analysis: ScreenplayAnalysis | None = None
    parallel_research: ParallelResearch | None = None
    budget_analysis: BudgetAnalysis | None = None