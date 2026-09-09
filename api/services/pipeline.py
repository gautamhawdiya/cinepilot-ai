import asyncio
import logging
import os
import uuid
from pathlib import Path

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.workflow._errors import DynamicNodeFailError
from google.genai import types
from pydantic import BaseModel

from agents.pipeline.agent import production_pipeline_agent, replan_pipeline_agent
from pdf.call_sheet_pdf import generate_call_sheet_pdf
from tools.image_generation import generate_scene_image_to_path
from schemas.budget import BudgetAnalysis
from schemas.call_sheet import CallSheet
from schemas.production_plan import ProductionPlan
from schemas.production_research import ProductionResearch
from schemas.screenplay import ScreenplayAnalysis
from schemas.storyboard import Storyboard

from api.schemas import ProjectStatus, StageStatus, ProjectState
from api.services.project_outputs import (
    load_budget_analysis,
    load_production_research,
    load_screenplay_analysis,
)
from api.services.project_store import project_store


PROJECT_ROOT = Path(__file__).resolve().parents[2]
logger = logging.getLogger(__name__)

# The image model's quota only tolerates a couple of requests in flight at
# once (confirmed: 16 fired concurrently succeeded for only 2 -- see
# tools/image_generation.py's retry-with-backoff, which handles the rest).
_MAX_CONCURRENT_IMAGE_REQUESTS = 2

# The ADK agent's name maps to the pipeline stage it drives. This also
# equals that agent's `output_key`, so ADK's own state_delta is keyed by
# the same names as api.schemas.DEFAULT_STAGES (minus "pdf", which is a
# deterministic render step with no agent behind it).
_AGENT_TO_STAGE = {
    "script_agent": "screenplay_analysis",
    "budget_agent": "budget_analysis",
    "production_research_agent": "production_research",
    "production_plan_agent": "production_plan",
    "storyboard_agent": "storyboard",
    "call_sheet_agent": "call_sheet",
}

_STAGE_SCHEMAS: dict[str, type[BaseModel]] = {
    "screenplay_analysis": ScreenplayAnalysis,
    "budget_analysis": BudgetAnalysis,
    "production_research": ProductionResearch,
    "production_plan": ProductionPlan,
    "storyboard": Storyboard,
    "call_sheet": CallSheet,
}

# Stages a producer re-plan recomputes. Screenplay analysis, budget and
# research describe the script and the world, not the plan, so a new
# constraint doesn't invalidate them.
REPLAN_STAGES = (
    "production_plan",
    "storyboard",
    "call_sheet",
    "storyboard_images",
    "pdf",
)

_APP_NAME = "cinepilot-api"
_USER_ID = "local_user"

# The first outbound TLS connection of a fresh process occasionally hangs
# indefinitely rather than failing (observed on a dev machine with HTTPS
# interception). Without a bound, a project sits "running" forever with no
# error -- far worse than a visible failure. The first workflow event normally
# arrives in 10-20s, so this only trips on a genuinely stuck connection.
_FIRST_EVENT_TIMEOUT_SECONDS = 90


class ColdStartTimeout(Exception):
    """The workflow produced no events before the cold-start deadline."""


def _set_stage(project: ProjectState, name: str, status: StageStatus, error: str | None = None):
    project.current_stage = name if status in {StageStatus.RUNNING, StageStatus.FAILED} else project.current_stage
    project.stages[name].status = status
    project.stages[name].error = error
    project_store.update(project)


def _project_dir(project_id: str) -> Path:
    output_dir = PROJECT_ROOT / "outputs" / "projects" / project_id
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


async def _build_runner(agent, session_id: str, state: dict | None = None) -> Runner:
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=_APP_NAME,
        user_id=_USER_ID,
        session_id=session_id,
        state=state,
    )
    return Runner(
        agent=agent,
        app_name=_APP_NAME,
        session_service=session_service,
    )


async def _consume_agent_events(
    runner: Runner,
    session_id: str,
    message: types.Content,
    project: ProjectState,
    output_dir: Path,
    running_stages: set[str],
    validated: dict[str, BaseModel],
) -> None:
    """Drive one ADK workflow, mirroring its event stream onto stage status
    and persisting each stage's validated output as it lands."""
    stream = runner.run_async(
        user_id=_USER_ID,
        session_id=session_id,
        new_message=message,
    ).__aiter__()

    awaiting_first_event = True

    while True:
        try:
            if awaiting_first_event:
                event = await asyncio.wait_for(
                    stream.__anext__(), _FIRST_EVENT_TIMEOUT_SECONDS
                )
            else:
                event = await stream.__anext__()
        except StopAsyncIteration:
            break
        except TimeoutError as exc:
            await stream.aclose()
            raise ColdStartTimeout(
                "The model connection did not respond within "
                f"{_FIRST_EVENT_TIMEOUT_SECONDS}s."
            ) from exc

        awaiting_first_event = False

        stage = _AGENT_TO_STAGE.get(event.author)
        if stage is None:
            continue

        if stage not in running_stages and project.stages[stage].status != StageStatus.COMPLETED:
            running_stages.add(stage)
            _set_stage(project, stage, StageStatus.RUNNING)

        if not event.is_final_response():
            continue
        if not event.actions or not event.actions.state_delta:
            continue
        if stage not in event.actions.state_delta:
            continue

        schema = _STAGE_SCHEMAS[stage]
        model = schema.model_validate(event.actions.state_delta[stage])
        validated[stage] = model

        if stage == "screenplay_analysis":
            project.title = model.title

        (output_dir / f"{stage}.json").write_text(
            model.model_dump_json(indent=2), encoding="utf-8"
        )
        running_stages.discard(stage)
        _set_stage(project, stage, StageStatus.COMPLETED)


async def _run_workflow(
    agent,
    session_id: str,
    message: types.Content,
    project: ProjectState,
    output_dir: Path,
    running_stages: set[str],
    validated: dict[str, BaseModel],
    seed_state: dict | None = None,
) -> None:
    """Run a workflow, retrying once if the connection never woke up.

    No events means no stage was touched, so a retry starts from a clean slate
    rather than resuming a half-applied run.
    """
    for attempt in (1, 2):
        runner = await _build_runner(
            agent, f"{session_id}-a{attempt}", state=seed_state
        )
        try:
            await _consume_agent_events(
                runner,
                f"{session_id}-a{attempt}",
                message,
                project,
                output_dir,
                running_stages,
                validated,
            )
            return
        except ColdStartTimeout:
            if attempt == 2:
                raise
            logger.warning(
                "Workflow produced no events in %ss; retrying once.",
                _FIRST_EVENT_TIMEOUT_SECONDS,
            )


def _shot_image_path(output_dir: Path, scene_number: int, shot_number: int) -> Path:
    return (
        output_dir
        / "storyboard_images"
        / f"scene_{scene_number:02d}_shot_{shot_number:02d}.png"
    )


def _images_enabled() -> bool:
    return os.environ.get(
        "ENABLE_STORYBOARD_IMAGES", "true"
    ).strip().lower() not in {"0", "false", "no"}


async def _generate_images(
    shots: list[tuple[int, int, str]], output_dir: Path, patient: bool = False
) -> tuple[int, str | None]:
    """Generate a batch of shot images, bounded by the model's rate limit.

    Returns (succeeded, last_error). Never raises: a missing frame degrades to
    the UI's shot-spec placeholder rather than failing the project.
    """
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_IMAGE_REQUESTS)

    async def _one(scene_number: int, shot_number: int, prompt: str):
        async with semaphore:
            return await asyncio.to_thread(
                generate_scene_image_to_path,
                prompt,
                _shot_image_path(output_dir, scene_number, shot_number),
                patient,
            )

    results = await asyncio.gather(
        *(_one(scene, shot, prompt) for scene, shot, prompt in shots),
        return_exceptions=True,
    )

    succeeded = 0
    last_error = None
    for result in results:
        if isinstance(result, Exception):
            logger.warning("Storyboard image generation failed: %s", result)
            last_error = str(result)
        else:
            succeeded += 1

    return succeeded, last_error


# Background per-shot image tasks, held so the event loop doesn't collect them
# mid-flight.
_background_image_tasks: set[asyncio.Task] = set()


async def _generate_remaining_shot_images(
    project_id: str, output_dir: Path, storyboard: Storyboard
) -> None:
    """Fill in every shot beyond each scene's key frame, after the pipeline has
    already reported completion.

    Generating all shots inline pushed a 16-shot run past 9 minutes with
    several permanent 429s, which is unusable during a live demo. Doing it here
    means the package is ready in the usual ~3 minutes and the remaining frames
    stream in behind it.
    """
    shots = [
        (scene.scene_number, shot.shot_number, shot.image_prompt)
        for scene in storyboard.scenes
        for shot in scene.shots[1:]
    ]

    try:
        if shots:
            succeeded, _ = await _generate_images(shots, output_dir, patient=True)
            logger.info(
                "Background storyboard frames: %d/%d generated for %s",
                succeeded,
                len(shots),
                project_id,
            )
    finally:
        project = project_store.get(project_id)
        if project is not None:
            project.images_pending = False
            project_store.update(project)


def _start_remaining_image_generation(
    project_id: str, output_dir: Path, storyboard: Storyboard
) -> None:
    if not _images_enabled() or not any(
        len(scene.shots) > 1 for scene in storyboard.scenes
    ):
        return

    project = project_store.get(project_id)
    if project is not None:
        project.images_pending = True
        project_store.update(project)

    task = asyncio.create_task(
        _generate_remaining_shot_images(project_id, output_dir, storyboard)
    )
    _background_image_tasks.add(task)
    task.add_done_callback(_background_image_tasks.discard)


async def _generate_storyboard_images(
    project: ProjectState, output_dir: Path, storyboard: Storyboard
) -> None:
    """One representative image per scene (its first shot's prompt), not one
    per shot. Real quota testing showed the image model's rate limit is strict
    enough that even with retry-with-backoff and bounded concurrency,
    one-per-shot pushed a 16-shot run past 9 minutes for this stage alone with
    several permanent failures. This is a plain Gemini call, not agentic
    reasoning, so it's a Python step rather than an ADK agent. Enhancement
    only: a failure here must not block the call sheet or PDF, which are
    already validated by this point.
    """
    _set_stage(project, "storyboard_images", StageStatus.RUNNING)

    if not _images_enabled():
        logger.info("Storyboard image generation disabled via ENABLE_STORYBOARD_IMAGES.")
        _set_stage(project, "storyboard_images", StageStatus.COMPLETED)
        return

    key_frames = [
        (scene.scene_number, scene.shots[0].shot_number, scene.shots[0].image_prompt)
        for scene in storyboard.scenes
        if scene.shots
    ]
    generated_count, last_image_error = await _generate_images(key_frames, output_dir)

    if generated_count > 0:
        _set_stage(project, "storyboard_images", StageStatus.COMPLETED)
    else:
        _set_stage(
            project,
            "storyboard_images",
            StageStatus.FAILED,
            last_image_error or "No storyboard images could be generated.",
        )


def _render_call_sheet_pdf(
    project: ProjectState, output_dir: Path, call_sheet: CallSheet
) -> None:
    # Deterministic renderer; no LLM call.
    _set_stage(project, "pdf", StageStatus.RUNNING)
    generate_call_sheet_pdf(call_sheet, output_dir / "call_sheet.pdf")
    _set_stage(project, "pdf", StageStatus.COMPLETED)


def _record_failure(
    project_id: str,
    project: ProjectState,
    exc: Exception,
    running_stages: set[str],
) -> None:
    project = project_store.get(project_id) or project

    # ADK wraps a failing agent's error in DynamicNodeFailError, whose
    # message names the failing node and whose .error carries the real
    # underlying exception -- giving precise per-agent attribution even
    # when the failure happened inside a concurrent ParallelAgent group.
    culprit_stage = None
    for agent_name, stage_name in _AGENT_TO_STAGE.items():
        if agent_name in str(exc):
            culprit_stage = stage_name
            break

    underlying = exc.error if isinstance(exc, DynamicNodeFailError) else exc
    message = str(underlying)

    stages_to_fail = set(running_stages)
    if culprit_stage:
        stages_to_fail.add(culprit_stage)
    if not stages_to_fail:
        stages_to_fail.add(project.current_stage or "pdf")

    for stage_name in stages_to_fail:
        if stage_name not in project.stages:
            continue
        if stage_name == culprit_stage or culprit_stage is None:
            stage_message = message
        else:
            stage_message = f"Aborted: {culprit_stage} failed."
        _set_stage(project, stage_name, StageStatus.FAILED, stage_message)

    project.current_stage = None
    project.status = ProjectStatus.FAILED
    project.error = message
    project_store.update(project)


async def run_project_pipeline(project_id: str) -> None:
    project = project_store.get(project_id)
    if project is None:
        return

    output_dir = _project_dir(project_id)

    # Stages whose agent has started but not yet reached a validated final
    # output. Used to attribute a mid-run failure to the right stage(s) --
    # including both sides of the budget/research pair, which run
    # concurrently under one ADK ParallelAgent and can therefore both be
    # in flight when a failure happens.
    running_stages: set[str] = set()
    validated: dict[str, BaseModel] = {}

    try:
        project.status = ProjectStatus.RUNNING
        project.error = None
        project_store.update(project)

        pdf_bytes = Path(project.screenplay_path).read_bytes()

        message = types.Content(
            role="user",
            parts=[
                types.Part(
                    text=(
                        "Analyze this screenplay PDF and produce the full "
                        "CinePilot production package."
                    )
                ),
                types.Part(
                    inline_data=types.Blob(
                        mime_type="application/pdf",
                        data=pdf_bytes,
                    )
                ),
            ],
        )

        await _run_workflow(
            production_pipeline_agent,
            f"project-{project_id}",
            message,
            project,
            output_dir,
            running_stages,
            validated,
        )

        await _generate_storyboard_images(project, output_dir, validated["storyboard"])
        _render_call_sheet_pdf(project, output_dir, validated["call_sheet"])

        project.status = ProjectStatus.COMPLETED
        project.current_stage = None
        project_store.update(project)

        # The package is complete and downloadable at this point; the rest of
        # the per-shot frames stream in behind it.
        _start_remaining_image_generation(
            project_id, output_dir, validated["storyboard"]
        )

    except Exception as exc:
        _record_failure(project_id, project, exc, running_stages)


async def replan_project(project_id: str, directive: str) -> None:
    """Re-run planning onward under a new producer constraint.

    The screenplay analysis, budget and research from the first pass are still
    valid, so they're seeded into the new session's state rather than
    recomputed -- the re-plan is the same agents reasoning again under a
    changed constraint, not a fresh pipeline.
    """
    project = project_store.get(project_id)
    if project is None:
        return

    output_dir = _project_dir(project_id)
    running_stages: set[str] = set()
    validated: dict[str, BaseModel] = {}

    try:
        project.status = ProjectStatus.RUNNING
        project.error = None
        project.producer_directive = directive
        for stage_name in REPLAN_STAGES:
            project.stages[stage_name].status = StageStatus.PENDING
            project.stages[stage_name].error = None
        project_store.update(project)

        seed_state = {
            "screenplay_analysis": load_screenplay_analysis(project_id).model_dump(),
            "budget_analysis": load_budget_analysis(project_id).model_dump(),
            "production_research": load_production_research(project_id).model_dump(),
            "producer_directive": directive,
        }

        message = types.Content(
            role="user",
            parts=[
                types.Part(
                    text=(
                        "Re-plan this production under the producer's new "
                        "directive, then update the storyboard and call sheet "
                        "to match."
                    )
                )
            ],
        )

        # A fresh session id per re-plan, so an earlier pass's conversation
        # state can't leak into this one.
        await _run_workflow(
            replan_pipeline_agent,
            f"project-{project_id}-replan-{uuid.uuid4().hex[:8]}",
            message,
            project,
            output_dir,
            running_stages,
            validated,
            seed_state=seed_state,
        )

        await _generate_storyboard_images(project, output_dir, validated["storyboard"])
        _render_call_sheet_pdf(project, output_dir, validated["call_sheet"])

        project.status = ProjectStatus.COMPLETED
        project.current_stage = None
        project_store.update(project)

        # The package is complete and downloadable at this point; the rest of
        # the per-shot frames stream in behind it.
        _start_remaining_image_generation(
            project_id, output_dir, validated["storyboard"]
        )

    except Exception as exc:
        _record_failure(project_id, project, exc, running_stages)


def start_project_pipeline(project_id: str) -> asyncio.Task:
    return asyncio.create_task(run_project_pipeline(project_id))


def start_project_replan(project_id: str, directive: str) -> asyncio.Task:
    return asyncio.create_task(replan_project(project_id, directive))
