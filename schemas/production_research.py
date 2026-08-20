from pydantic import BaseModel, Field


class ProductionResearchFinding(BaseModel):
    topic: str
    finding: str
    source_title: str
    source_url: str
    production_impact: str
    confidence: str
    requires_local_verification: bool


class ProductionResearch(BaseModel):
    research_topic: str
    findings: list[ProductionResearchFinding] = Field(default_factory=list)
    production_recommendations: list[str] = Field(default_factory=list)
