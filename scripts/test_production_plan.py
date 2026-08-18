import sys
from pathlib import Path
import json
import asyncio

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from schemas.screenplay import ScreenplayAnalysis
from schemas.budget import BudgetAnalysis
from schemas.parallel import ParallelResearch
from schemas.production_plan import ProductionPlan

from agents.production_plan.agent import production_plan_agent


load_dotenv(PROJECT_ROOT / ".env")


APP_NAME = "cinepilot-production-plan"
USER_ID = "local_user"
SESSION_ID = "production_plan_test"


def load_json(filename):
    path = PROJECT_ROOT / "test_data" / filename

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


async def main():

    print("\n🎬 CinePilot AI - Production Planner")
    print("========================================")

    # ---------------------------------------------------------
    # Load screenplay
    # ---------------------------------------------------------

    screenplay_data = load_json(
        "sample_screenplay_analysis.json"
    )

    screenplay = ScreenplayAnalysis.model_validate(
        screenplay_data
    )

    print(f"\nScreenplay: {screenplay.title}")
    print(f"Scenes: {screenplay.scene_count}")
    print(f"Shoot Days: {screenplay.estimated_shoot_days}")

    # ---------------------------------------------------------
    # Load budget
    # ---------------------------------------------------------

    budget_path = (
        PROJECT_ROOT
        / "test_data"
        / "sample_budget_analysis.json"
    )

    with open(
        budget_path,
        "r",
        encoding="utf-8",
    ) as file:

        budget_data = json.load(file)

    budget = BudgetAnalysis.model_validate(
        budget_data
    )

    print(
        f"Budget: "
        f"{budget.currency} "
        f"{budget.total_estimated_cost:,.0f}"
    )

    # ---------------------------------------------------------
    # Load Parallel research
    # ---------------------------------------------------------

    research_path = (
        PROJECT_ROOT
        / "test_data"
        / "sample_parallel_research.json"
    )

    with open(
        research_path,
        "r",
        encoding="utf-8",
    ) as file:

        research_data = json.load(file)

    research = ParallelResearch.model_validate(
        research_data
    )

    print(
        f"Research Results: "
        f"{len(research.results)}"
    )

    # ---------------------------------------------------------
    # Build prompt
    # ---------------------------------------------------------

    prompt = f"""
Create a production plan for the screenplay.

SCREENPLAY ANALYSIS:

{screenplay.model_dump_json(indent=2)}


BUDGET ANALYSIS:

{budget.model_dump_json(indent=2)}


PARALLEL RESEARCH:

{research.model_dump_json(indent=2)}


Use all three inputs.

Do not invent prices.

If a researched resource does not contain
a price, state that a quote is required.

Return ONLY valid JSON matching the
ProductionPlan schema.
"""

    # ---------------------------------------------------------
    # ADK session
    # ---------------------------------------------------------

    session_service = InMemorySessionService()

    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )

    runner = Runner(
        agent=production_plan_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    message = types.Content(
        role="user",
        parts=[
            types.Part(text=prompt)
        ],
    )

    # ---------------------------------------------------------
    # Execute agent
    # ---------------------------------------------------------

    print(
        "\n🤖 Generating production plan..."
    )

    final_text = None

    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=SESSION_ID,
        new_message=message,
    ):

        if event.is_final_response():

            if event.content and event.content.parts:

                for part in event.content.parts:

                    if part.text:
                        final_text = part.text
                        break

    if not final_text:

        raise RuntimeError(
            "Production Plan Agent returned no response."
        )

    # ---------------------------------------------------------
    # Validate
    # ---------------------------------------------------------

    print(
        "\n========== RAW PRODUCTION PLAN ==========\n"
    )

    print(final_text)

    print(
        "\n========== VALIDATING ==========\n"
    )

    try:

        plan = ProductionPlan.model_validate_json(
            final_text
        )

    except Exception as exc:

        print(
            "❌ ProductionPlan validation failed:"
        )

        print(exc)

        raise

    print(
        "✅ ProductionPlan validation successful!"
    )

    print(
        "\n========== VALIDATED PRODUCTION PLAN ==========\n"
    )

    print(
        plan.model_dump_json(
            indent=2
        )
    )


if __name__ == "__main__":
    asyncio.run(main())