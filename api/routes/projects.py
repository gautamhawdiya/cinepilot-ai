import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import ValidationError

from api.schemas import ProjectState, ProjectStatus
from api.services.pipeline import start_project_pipeline
from api.services.project_outputs import (
    load_production_plan,
    load_production_research,
    load_storyboard,
)
from api.services.project_store import project_store
from schemas.production_plan import ProductionPlan
from schemas.production_research import ProductionResearch
from schemas.storyboard import Storyboard

router = APIRouter(prefix="/api/projects", tags=["projects"])
PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_ROOT = PROJECT_ROOT / "outputs" / "projects"


@router.post("", response_model=ProjectState, status_code=status.HTTP_201_CREATED)
async def create_project(screenplay: UploadFile = File(...)):
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
async def run_project(project_id: str):
    project = project_store.get(project_id)
    if project is None:
        raise HTTPException(404, "Project not found.")
    if project.status == ProjectStatus.RUNNING:
        return project
    if project.status == ProjectStatus.COMPLETED:
        raise HTTPException(409, "Project pipeline is already completed.")

    start_project_pipeline(project_id)
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
