from pathlib import Path

from schemas.budget import BudgetAnalysis
from schemas.call_sheet import CallSheet
from schemas.production_plan import ProductionPlan
from schemas.production_research import ProductionResearch
from schemas.screenplay import ScreenplayAnalysis
from schemas.storyboard import Storyboard


PROJECT_OUTPUT_ROOT = (
    Path(__file__).resolve().parents[2] / "outputs" / "projects"
)


def load_screenplay_analysis(project_id: str) -> ScreenplayAnalysis:
    """Load and validate a project's persisted screenplay analysis."""
    screenplay_path = (
        PROJECT_OUTPUT_ROOT / project_id / "screenplay_analysis.json"
    )
    if not screenplay_path.is_file():
        raise FileNotFoundError(screenplay_path)

    return ScreenplayAnalysis.model_validate_json(
        screenplay_path.read_text(encoding="utf-8")
    )


def load_budget_analysis(project_id: str) -> BudgetAnalysis:
    """Load and validate a project's persisted budget analysis."""
    budget_path = PROJECT_OUTPUT_ROOT / project_id / "budget_analysis.json"
    if not budget_path.is_file():
        raise FileNotFoundError(budget_path)

    return BudgetAnalysis.model_validate_json(
        budget_path.read_text(encoding="utf-8")
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


def load_call_sheet(project_id: str) -> CallSheet:
    """Load and validate a project's persisted call sheet."""
    call_sheet_path = PROJECT_OUTPUT_ROOT / project_id / "call_sheet.json"
    if not call_sheet_path.is_file():
        raise FileNotFoundError(call_sheet_path)

    return CallSheet.model_validate_json(
        call_sheet_path.read_text(encoding="utf-8")
    )


def get_call_sheet_pdf_path(project_id: str) -> Path:
    """Return the path to a project's existing call sheet PDF."""
    pdf_path = PROJECT_OUTPUT_ROOT / project_id / "call_sheet.pdf"
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)

    return pdf_path


def list_storyboard_images(project_id: str) -> list[tuple[int, int]]:
    """Return the (scene_number, shot_number) pairs that have a generated
    storyboard preview image, sorted ascending. Empty if none were
    generated (e.g. image generation failed, or the project hasn't reached
    that stage yet)."""
    images_dir = PROJECT_OUTPUT_ROOT / project_id / "storyboard_images"
    if not images_dir.is_dir():
        return []

    pairs = []
    for path in images_dir.glob("scene_*_shot_*.png"):
        parts = path.stem.split("_")
        if len(parts) == 4 and parts[1].isdigit() and parts[3].isdigit():
            pairs.append((int(parts[1]), int(parts[3])))

    return sorted(pairs)


def get_storyboard_image_path(
    project_id: str, scene_number: int, shot_number: int
) -> Path:
    """Return the path to one shot's generated storyboard preview image."""
    image_path = (
        PROJECT_OUTPUT_ROOT
        / project_id
        / "storyboard_images"
        / f"scene_{scene_number:02d}_shot_{shot_number:02d}.png"
    )
    if not image_path.is_file():
        raise FileNotFoundError(image_path)

    return image_path
