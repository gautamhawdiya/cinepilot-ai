from pathlib import Path

from schemas.production_plan import ProductionPlan
from schemas.production_research import ProductionResearch
from schemas.storyboard import Storyboard


PROJECT_OUTPUT_ROOT = (
    Path(__file__).resolve().parents[2] / "outputs" / "projects"
)


def load_production_research(project_id: str) -> ProductionResearch:
    """Load and validate a project's persisted production research."""
    research_path = (
        PROJECT_OUTPUT_ROOT / project_id / "production_research.json"
    )
    if not research_path.is_file():
        raise FileNotFoundError(research_path)

    return ProductionResearch.model_validate_json(
        research_path.read_text(encoding="utf-8")
    )


def load_production_plan(project_id: str) -> ProductionPlan:
    """Load and validate a project's persisted production plan."""
    plan_path = PROJECT_OUTPUT_ROOT / project_id / "production_plan.json"
    if not plan_path.is_file():
        raise FileNotFoundError(plan_path)

    return ProductionPlan.model_validate_json(
        plan_path.read_text(encoding="utf-8")
    )


def load_storyboard(project_id: str) -> Storyboard:
    """Load and validate a project's persisted storyboard plan."""
    storyboard_path = PROJECT_OUTPUT_ROOT / project_id / "storyboard.json"
    if not storyboard_path.is_file():
        raise FileNotFoundError(storyboard_path)

    return Storyboard.model_validate_json(
        storyboard_path.read_text(encoding="utf-8")
    )
