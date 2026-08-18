from pydantic import BaseModel, Field


class Character(BaseModel):
    name: str
    description: str = ""


class Scene(BaseModel):
    scene_number: int
    heading: str
    location: str = ""
    time_of_day: str = ""
    characters: list[str] = []
    summary: str = ""


class ScreenplayAnalysis(BaseModel):
    title: str
    genre: str = ""
    logline: str = ""

    characters: list[Character] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    props: list[str] = Field(default_factory=list)
    vehicles: list[str] = Field(default_factory=list)
    vfx_requirements: list[str] = Field(default_factory=list)

    scenes: list[Scene] = Field(default_factory=list)

    scene_count: int = 0
    estimated_shoot_days: int = 0