from pydantic import BaseModel, Field


class ParallelResult(BaseModel):
    title: str
    url: str
    snippet: str = ""
    relevance: str = ""
    price: str | None = None
    location: str | None = None


class ParallelResearch(BaseModel):
    objective: str
    queries: list[str] = Field(default_factory=list)
    results: list[ParallelResult] = Field(default_factory=list)