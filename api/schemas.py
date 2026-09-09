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
    "storyboard_images",
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

    # The most recent producer constraint applied via re-planning, if any.
    producer_directive: str | None = None

    # True while the remaining per-shot storyboard frames are still being
    # generated in the background, after the pipeline itself has completed.
    images_pending: bool = False

    error: str | None = None
