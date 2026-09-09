import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError

from api.schemas import ProjectState, ProjectStatus, StageStatus
from api.services.pipeline import start_project_pipeline, start_project_replan
from api.services.rate_limit import enforce_run_limit, enforce_upload_limit
from api.services.project_outputs import (
    get_call_sheet_pdf_path,
    get_storyboard_image_path,
    list_storyboard_images,
    load_budget_analysis,
    load_call_sheet,
    load_production_plan,
    load_production_research,
    load_screenplay_analysis,
    load_storyboard,
)
from api.services.project_store import project_store
from schemas.budget import BudgetAnalysis
from schemas.call_sheet import CallSheet
from schemas.production_plan import ProductionPlan
from schemas.production_research import ProductionResearch
from schemas.screenplay import ScreenplayAnalysis
from schemas.storyboard import Storyboard

router = APIRouter(prefix="/api/projects", tags=["projects"])
PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_ROOT = PROJECT_ROOT / "outputs" / "projects"


@router.post("", response_model=ProjectState, status_code=status.HTTP_201_CREATED)
async def create_project(request: Request, screenplay: UploadFile = File(...)):
    enforce_upload_limit(request)

    filename = screenplay.filename or "screenplay.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only screenplay PDF files are currently supported.")

    data = await screenplay.read()
    if not data:
        raise HTTPException(400, "Uploaded screenplay is empty.")

    project_id = f"proj_{uuid.uuid4().hex[:12]}"
    project_dir = UPLOAD_ROOT / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    screenplay_path = project_dir / filename
    screenplay_path.write_bytes(data)

    project = ProjectState(
        project_id=project_id,
        screenplay_filename=filename,
        screenplay_path=str(screenplay_path),
    )
    return project_store.create(project)


@router.post("/{project_id}/run", response_model=ProjectState, status_code=status.HTTP_202_ACCEPTED)
async def run_project(project_id: str, request: Request):
    project = project_store.get(project_id)
    if project is None:
        raise HTTPException(404, "Project not found.")
    if project.status == ProjectStatus.RUNNING:
        return project
    if project.status == ProjectStatus.COMPLETED:
        raise HTTPException(409, "Project pipeline is already completed.")

    enforce_run_limit(request)

    start_project_pipeline(project_id)
    project.status = ProjectStatus.RUNNING
    project_store.update(project)
    return project


class ReplanRequest(BaseModel):
    directive: str = Field(min_length=3, max_length=500)


@router.post(
    "/{project_id}/replan",
    response_model=ProjectState,
    status_code=status.HTTP_202_ACCEPTED,
)
async def replan_project_endpoint(
    project_id: str, body: ReplanRequest, request: Request
):
    """Re-plan an already-generated package under a new producer constraint.

    Only the plan, storyboard and call sheet are recomputed -- the screenplay
    analysis, budget and research still describe the same script and world.
    """
    project = project_store.get(project_id)
    if project is None:
        raise HTTPException(404, "Project not found.")
    if project.status == ProjectStatus.RUNNING:
        raise HTTPException(409, "This project is already running.")
    if project.stages["production_research"].status != StageStatus.COMPLETED:
        raise HTTPException(
            409,
            "Re-planning needs a completed first pass to build on.",
        )

    enforce_run_limit(request)

    start_project_replan(project_id, body.directive.strip())
    project.status = ProjectStatus.RUNNING
    project_store.update(project)
    return project


@router.get("/{project_id}", response_model=ProjectState)
async def get_project(project_id: str):
    project = project_store.get(project_id)
    if project is None:
        raise HTTPException(404, "Project not found.")
    return project


@router.get("/{project_id}/status", response_model=ProjectState)
async def get_project_status(project_id: str):
    project = project_store.get(project_id)
    if project is None:
        raise HTTPException(404, "Project not found.")
    return project


@router.get("/{project_id}/screenplay", response_model=ScreenplayAnalysis)
async def get_project_screenplay(project_id: str):
    project = project_store.get(project_id)
    if project is None:
        raise HTTPException(404, "Project not found.")

    try:
        return load_screenplay_analysis(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            404, "Screenplay analysis is not available yet."
        ) from exc
    except ValidationError as exc:
        raise HTTPException(
            500, "Stored screenplay analysis failed validation."
        ) from exc


@router.get("/{project_id}/budget", response_model=BudgetAnalysis)
async def get_project_budget(project_id: str):
    project = project_store.get(project_id)
    if project is None:
        raise HTTPException(404, "Project not found.")

    try:
        return load_budget_analysis(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            404, "Budget analysis is not available yet."
        ) from exc
    except ValidationError as exc:
        raise HTTPException(
            500, "Stored budget analysis failed validation."
        ) from exc


@router.get("/{project_id}/research", response_model=ProductionResearch)
async def get_project_research(project_id: str):
    project = project_store.get(project_id)
    if project is None:
        raise HTTPException(404, "Project not found.")

    try:
        return load_production_research(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            404, "Production research is not available yet."
        ) from exc
    except ValidationError as exc:
        raise HTTPException(
            500, "Stored production research failed validation."
        ) from exc


@router.get("/{project_id}/plan", response_model=ProductionPlan)
async def get_project_plan(project_id: str):
    project = project_store.get(project_id)
    if project is None:
        raise HTTPException(404, "Project not found.")

    try:
        return load_production_plan(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            404, "Production plan is not available yet."
        ) from exc
    except ValidationError as exc:
        raise HTTPException(
            500, "Stored production plan failed validation."
        ) from exc


@router.get("/{project_id}/storyboard", response_model=Storyboard)
async def get_project_storyboard(project_id: str):
    project = project_store.get(project_id)
    if project is None:
        raise HTTPException(404, "Project not found.")

    try:
        return load_storyboard(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            404, "Storyboard is not available yet."
        ) from exc
    except ValidationError as exc:
        raise HTTPException(
            500, "Stored storyboard failed validation."
        ) from exc


@router.get("/{project_id}/storyboard/images")
async def get_project_storyboard_images(project_id: str):
    project = project_store.get(project_id)
    if project is None:
        raise HTTPException(404, "Project not found.")

    pairs = list_storyboard_images(project_id)
    return [
        {
            "scene_number": scene_number,
            "shot_number": shot_number,
            "url": (
                f"/api/projects/{project_id}/storyboard/images/"
                f"{scene_number}/{shot_number}"
            ),
        }
        for scene_number, shot_number in pairs
    ]


@router.get(
    "/{project_id}/storyboard/images/{scene_number}/{shot_number}",
    response_class=FileResponse,
)
async def get_project_storyboard_image(
    project_id: str, scene_number: int, shot_number: int
):
    project = project_store.get(project_id)
    if project is None:
        raise HTTPException(404, "Project not found.")

    try:
        image_path = get_storyboard_image_path(
            project_id, scene_number, shot_number
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            404, "No generated image is available for this shot."
        ) from exc

    return FileResponse(path=image_path, media_type="image/png")


@router.get("/{project_id}/call-sheet", response_model=CallSheet)
async def get_project_call_sheet(project_id: str):
    project = project_store.get(project_id)
    if project is None:
        raise HTTPException(404, "Project not found.")

    try:
        return load_call_sheet(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            404, "Call sheet is not available yet."
        ) from exc
    except ValidationError as exc:
        raise HTTPException(
            500, "Stored call sheet failed validation."
        ) from exc


@router.get("/{project_id}/call-sheet/pdf", response_class=FileResponse)
async def get_project_call_sheet_pdf(project_id: str):
    project = project_store.get(project_id)
    if project is None:
        raise HTTPException(404, "Project not found.")

    try:
        pdf_path = get_call_sheet_pdf_path(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            404, "Call sheet PDF is not available yet."
        ) from exc

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"{project_id}-call-sheet.pdf",
    )
