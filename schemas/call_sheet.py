from pydantic import BaseModel, ConfigDict, Field, model_validator


class CallSheetScene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_number: int
    heading: str
    summary: str

    estimated_shooting_time: str | None = None

    characters_present: list[str] = Field(
        default_factory=list
    )

    props: list[str] = Field(
        default_factory=list
    )

    vfx_requirements: list[str] = Field(
        default_factory=list
    )

    notes: str | None = None


class CallSheetCast(BaseModel):
    model_config = ConfigDict(extra="forbid")

    character_name: str
    actor_name: str = "TBD"


class CallSheetCrew(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    name: str = "TBD"


class CallSheetShootDay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_number: int

    date: str | None = None

    location: str

    crew_call: str | None = None

    first_shot: str | None = None

    lunch_break: str | None = None

    wrap: str | None = None

    scenes_scheduled: list[CallSheetScene] = Field(
        default_factory=list
    )

    cast_on_call: list[str] = Field(
        default_factory=list
    )

    crew_on_call: list[str] = Field(
        default_factory=list
    )

    required_props: list[str] = Field(
        default_factory=list
    )

    required_equipment: list[str] = Field(
        default_factory=list
    )

    production_notes: list[str] = Field(
        default_factory=list
    )

    safety_and_logistics: list[str] = Field(
        default_factory=list
    )


class CallSheet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    call_sheet_id: str = "TBD"

    project_title: str = "TBD"

    production_company: str | None = None

    project_manager: str = "TBD"

    date: str | None = None

    genre: str | None = None

    logline: str | None = None

    shoot_days_total: int | None = None

    shoot_days: list[CallSheetShootDay] = Field(
        default_factory=list
    )

    cast_list: list[CallSheetCast] = Field(
        default_factory=list
    )

    crew_list: list[CallSheetCrew] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_and_calculate(self):

        actual_days = len(self.shoot_days)

        # Always derive this from the actual schedule.
        self.shoot_days_total = actual_days

        # A call sheet with shoot days must actually contain
        # scheduled scenes.
        if actual_days > 0:

            total_scenes = sum(
                len(day.scenes_scheduled)
                for day in self.shoot_days
            )

            if total_scenes == 0:
                raise ValueError(
                    "CallSheet contains shoot days "
                    "but no scheduled scenes."
                )

        return self