from enum import Enum

from pydantic import BaseModel, Field


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ProjectStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StageState(BaseModel):
    status: StageStatus = StageStatus.PENDING
    error: str | None = None


DEFAULT_STAGES = (
    "screenplay_analysis",
    "budget_analysis",
    "production_research",
    "production_plan",
    "storyboard",
    "call_sheet",
    "pdf",
)


class ProjectState(BaseModel):
    project_id: str
    title: str = "TBD"
    screenplay_filename: str
    screenplay_path: str

    status: ProjectStatus = ProjectStatus.CREATED
    current_stage: str | None = None

    stages: dict[str, StageState] = Field(
        default_factory=lambda: {
            name: StageState() for name in DEFAULT_STAGES
        }
    )

    error: str | None = None
