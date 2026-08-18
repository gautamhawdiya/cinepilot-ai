from pydantic import BaseModel, Field, ConfigDict


class StoryboardShot(BaseModel):

    model_config = ConfigDict(extra="forbid")

    shot_number: int
    scene_number: int
    screenplay_evidence: str
    shot_type: str
    camera_angle: str
    camera_movement: str
    subject: str
    action: str
    visual_description: str
    lighting: str
    mood: str
    vfx_required: bool
    vfx_notes: str | None
    image_prompt: str


class StoryboardScene(BaseModel):

    model_config = ConfigDict(extra="forbid")

    scene_number: int
    scene_heading: str
    source_scene_summary: str
    visual_goal: str

    shots: list[StoryboardShot] = Field(
        ...,
        min_length=1
    )


class Storyboard(BaseModel):

    model_config = ConfigDict(extra="forbid")

    title: str

    visual_style: str

    cinematography_strategy: str

    scenes: list[StoryboardScene] = Field(
        ...,
        min_length=1
    )

    total_shots: int = Field(
        ...,
        ge=1
    )