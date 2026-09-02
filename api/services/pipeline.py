import asyncio
from pathlib import Path

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agents.budget.agent import budget_agent
from agents.call_sheet.agent import call_sheet_agent
from agents.production_plan.agent import production_plan_agent
from agents.production_research.agent import production_research_agent
from agents.script.agent import script_agent
from agents.storyboard.agent import storyboard_agent
from pdf.call_sheet_pdf import generate_call_sheet_pdf
from schemas.budget import BudgetAnalysis
from schemas.call_sheet import CallSheet
from schemas.production_plan import ProductionPlan
from schemas.production_research import ProductionResearch
from schemas.screenplay import ScreenplayAnalysis
from schemas.storyboard import Storyboard

from api.schemas import ProjectStatus, StageStatus, ProjectState
from api.services.project_store import project_store


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _clean_json(text: str) -> str:
    value = text.strip()
    if value.startswith("```json"):
        value = value[len("```json"):].strip()
    elif value.startswith("```"):
        value = value[len("```"):].strip()
    if value.endswith("```"):
        value = value[:-3].strip()
    return value


async def _run_agent(agent, prompt: str, session_suffix: str, pdf_bytes: bytes | None = None) -> str:
    service = InMemorySessionService()
    session_id = f"project-{session_suffix}"
    await service.create_session(
        app_name="cinepilot-api",
        user_id="local_user",
        session_id=session_id,
    )

    runner = Runner(
        agent=agent,
        app_name="cinepilot-api",
        session_service=service,
    )

    parts = [types.Part(text=prompt)]
    if pdf_bytes is not None:
        parts.append(
            types.Part(
                inline_data=types.Blob(
                    mime_type="application/pdf",
                    data=pdf_bytes,
                )
            )
        )

    message = types.Content(role="user", parts=parts)
    final_text = None

    async for event in runner.run_async(
        user_id="local_user",
        session_id=session_id,
        new_message=message,
    ):
        if not event.is_final_response():
            continue
        if not event.content or not event.content.parts:
            continue
        for part in event.content.parts:
            if part.text:
                final_text = part.text
                break

    if not final_text:
        raise RuntimeError(f"{agent.name} returned no final response.")

    return final_text


def _set_stage(project: ProjectState, name: str, status: StageStatus, error: str | None = None):
    project.current_stage = name if status in {StageStatus.RUNNING, StageStatus.FAILED} else project.current_stage
    project.stages[name].status = status
    project.stages[name].error = error
    project_store.update(project)


async def run_project_pipeline(project_id: str) -> None:
    project = project_store.get(project_id)
    if project is None:
        return

    try:
        project.status = ProjectStatus.RUNNING
        project.error = None
        project_store.update(project)

        pdf_bytes = Path(project.screenplay_path).read_bytes()

        # ------------------------------------------------------------
        # 1. Screenplay analysis
        # ------------------------------------------------------------
        _set_stage(project, "screenplay_analysis", StageStatus.RUNNING)
        script_text = await _run_agent(
            script_agent,
            "Analyze this screenplay PDF and return the complete screenplay analysis as JSON.",
            f"{project_id}-script",
            pdf_bytes,
        )
        screenplay = ScreenplayAnalysis.model_validate_json(_clean_json(script_text))
        project.title = screenplay.title
        output_dir = PROJECT_ROOT / "outputs" / "projects" / project_id
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "screenplay_analysis.json").write_text(
            screenplay.model_dump_json(indent=2), encoding="utf-8"
        )
        _set_stage(project, "screenplay_analysis", StageStatus.COMPLETED)

        # ------------------------------------------------------------
        # 2. Budget and research are independent after screenplay.
        # Run them concurrently to reduce total latency.
        # ------------------------------------------------------------
        _set_stage(project, "budget_analysis", StageStatus.RUNNING)
        _set_stage(project, "production_research", StageStatus.RUNNING)

        screenplay_json = screenplay.model_dump_json(indent=2)
        budget_prompt = f"""
Create a preliminary production budget using ONLY this validated screenplay analysis.
Do not analyze the original screenplay again.

SCREENPLAY ANALYSIS:
{screenplay_json}

Return ONLY valid JSON matching BudgetAnalysis.
"""

        research_prompt = f"""
Research current real-world production constraints relevant to this screenplay.
Use Parallel Search when external/current information is required.

SCREENPLAY ANALYSIS:
{screenplay_json}

Focus only on production-relevant information such as permits, location access,
filming restrictions, equipment restrictions, insurance/safety considerations,
filming hours, public access, and logistics.
Do not assume a production city that is not present in the screenplay.
Clearly mark location-specific information that requires local verification.
Return ONLY valid JSON matching the ProductionResearch output contract.
"""

        budget_task = _run_agent(budget_agent, budget_prompt, f"{project_id}-budget")
        research_task = _run_agent(production_research_agent, research_prompt, f"{project_id}-research")
        budget_text, research_text = await asyncio.gather(
            budget_task, research_task, return_exceptions=True
        )

        budget_error: Exception | None = (
            budget_text if isinstance(budget_text, Exception) else None
        )
        research_error: Exception | None = (
            research_text if isinstance(research_text, Exception) else None
        )

        budget: BudgetAnalysis | None = None
        if budget_error is None:
            try:
                budget = BudgetAnalysis.model_validate_json(_clean_json(budget_text))
            except Exception as exc:
                budget_error = exc

        research: ProductionResearch | None = None
        if research_error is None:
            try:
                research = ProductionResearch.model_validate_json(_clean_json(research_text))
            except Exception as exc:
                research_error = exc

        # These two stages share no ordering, so a failure in either must be
        # attributed to the stage that actually failed, and the sibling must
        # not be left stuck at "running" forever just because the pipeline
        # aborts before it gets a chance to reach "completed".
        if budget_error is not None or research_error is not None:
            if budget_error is not None:
                _set_stage(project, "budget_analysis", StageStatus.FAILED, str(budget_error))
            else:
                _set_stage(
                    project,
                    "budget_analysis",
                    StageStatus.FAILED,
                    "Aborted: production_research failed.",
                )

            if research_error is not None:
                _set_stage(project, "production_research", StageStatus.FAILED, str(research_error))
            else:
                _set_stage(
                    project,
                    "production_research",
                    StageStatus.FAILED,
                    "Aborted: budget_analysis failed.",
                )

            project.current_stage = None
            project.status = ProjectStatus.FAILED
            project.error = "; ".join(
                str(err) for err in (budget_error, research_error) if err is not None
            )
            project_store.update(project)
            return

        research_json = research.model_dump_json(indent=2)

        (output_dir / "budget_analysis.json").write_text(
            budget.model_dump_json(indent=2), encoding="utf-8"
        )
        (output_dir / "production_research.json").write_text(
            research_json, encoding="utf-8"
        )
        _set_stage(project, "budget_analysis", StageStatus.COMPLETED)
        _set_stage(project, "production_research", StageStatus.COMPLETED)

        # ------------------------------------------------------------
        # 3. Production plan
        # ------------------------------------------------------------
        _set_stage(project, "production_plan", StageStatus.RUNNING)
        plan_prompt = f"""
Create the practical production plan from these validated inputs.

SCREENPLAY ANALYSIS:
{screenplay_json}

BUDGET ANALYSIS:
{budget.model_dump_json(indent=2)}

PRODUCTION RESEARCH:
{research_json}

Use the research as evidence, preserving source URLs and verification requirements.
Do not invent prices, availability, locations, vendors, permits, or regulations.
Return ONLY valid JSON matching ProductionPlan.
"""
        plan_text = await _run_agent(
            production_plan_agent, plan_prompt, f"{project_id}-plan"
        )
        production_plan = ProductionPlan.model_validate_json(_clean_json(plan_text))
        (output_dir / "production_plan.json").write_text(
            production_plan.model_dump_json(indent=2), encoding="utf-8"
        )
        _set_stage(project, "production_plan", StageStatus.COMPLETED)

        # ------------------------------------------------------------
        # 4. Storyboard
        # ------------------------------------------------------------
        _set_stage(project, "storyboard", StageStatus.RUNNING)
        storyboard_prompt = f"""
Create a cinematic, production-ready storyboard from the validated screenplay analysis
and production plan below.

SCREENPLAY ANALYSIS:
{screenplay_json}

PRODUCTION PLAN:
{production_plan.model_dump_json(indent=2)}

Stay faithful to screenplay events and preserve recorded/future/video media boundaries.
Return ONLY valid JSON matching Storyboard.
"""
        storyboard_text = await _run_agent(
            storyboard_agent, storyboard_prompt, f"{project_id}-storyboard"
        )
        storyboard = Storyboard.model_validate_json(_clean_json(storyboard_text))
        (output_dir / "storyboard.json").write_text(
            storyboard.model_dump_json(indent=2), encoding="utf-8"
        )
        _set_stage(project, "storyboard", StageStatus.COMPLETED)

        # ------------------------------------------------------------
        # 5. Call sheet
        # ------------------------------------------------------------
        _set_stage(project, "call_sheet", StageStatus.RUNNING)
        call_prompt = f"""
Create the production call sheet from these validated inputs.

SCREENPLAY ANALYSIS:
{screenplay_json}

PRODUCTION PLAN:
{production_plan.model_dump_json(indent=2)}

STORYBOARD:
{storyboard.model_dump_json(indent=2)}

PRODUCTION RESEARCH:
{research_json}

Never invent dates, locations, people, story events, vendors, or unsupported rules.
Return ONLY valid JSON matching CallSheet.
"""
        call_text = await _run_agent(
            call_sheet_agent, call_prompt, f"{project_id}-call-sheet"
        )
        call_sheet = CallSheet.model_validate_json(_clean_json(call_text))
        (output_dir / "call_sheet.json").write_text(
            call_sheet.model_dump_json(indent=2), encoding="utf-8"
        )
        _set_stage(project, "call_sheet", StageStatus.COMPLETED)

        # ------------------------------------------------------------
        # 6. PDF renderer is deterministic; no LLM call.
        # ------------------------------------------------------------
        _set_stage(project, "pdf", StageStatus.RUNNING)
        pdf_path = output_dir / "call_sheet.pdf"
        generate_call_sheet_pdf(call_sheet, pdf_path)
        _set_stage(project, "pdf", StageStatus.COMPLETED)

        project.status = ProjectStatus.COMPLETED
        project.current_stage = None
        project_store.update(project)

    except Exception as exc:
        project = project_store.get(project_id) or project
        failed_stage = project.current_stage
        if failed_stage and failed_stage in project.stages:
            project.stages[failed_stage].status = StageStatus.FAILED
            project.stages[failed_stage].error = str(exc)
        project.status = ProjectStatus.FAILED
        project.error = str(exc)
        project_store.update(project)


def start_project_pipeline(project_id: str) -> asyncio.Task:
    return asyncio.create_task(run_project_pipeline(project_id))
