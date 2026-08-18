import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import asyncio
import json
import os

from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agents.director.agent import director_agent
from agents.budget.agent import budget_agent
from schemas.screenplay import ScreenplayAnalysis
from schemas.budget import BudgetAnalysis
from schemas.production import ProductionState


load_dotenv(PROJECT_ROOT / ".env")


APP_NAME = "cinepilot-production"
USER_ID = "local_user"
SESSION_ID = "production_session"


async def run_agent(
    agent,
    message: types.Content,
    app_name: str,
    user_id: str,
    session_id: str,
):
    """Run an ADK agent and return its final text response."""

    session_service = InMemorySessionService()

    await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
    )

    runner = Runner(
        agent=agent,
        app_name=app_name,
        session_service=session_service,
    )

    final_text = None

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=message,
    ):
        if event.is_final_response():

            if not event.content or not event.content.parts:
                continue

            for part in event.content.parts:
                if part.text:
                    final_text = part.text
                    break

    if not final_text:
        raise RuntimeError(
            f"{agent.name} did not return a final response."
        )

    return final_text


async def run_production(pdf_path: str):

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(
            f"Screenplay not found: {pdf_path}"
        )

    with open(pdf_path, "rb") as file:
        pdf_bytes = file.read()

    # ============================================================
    # STEP 1: SCRIPT ANALYSIS
    # ============================================================

    print("\n🎬 CinePilot AI Production Pipeline")
    print("====================================\n")

    print("📄 STEP 1 — Script Analysis")
    print("------------------------------------")

    script_message = types.Content(
        role="user",
        parts=[
            types.Part(
                text=(
                    "Analyze this screenplay PDF and return the "
                    "complete screenplay analysis as JSON."
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

    script_result = await run_agent(
        agent=director_agent,
        message=script_message,
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=f"{SESSION_ID}-script",
    )

    print("\n========== SCRIPT RESULT ==========\n")
    print(script_result)

    # ============================================================
    # STEP 2: VALIDATE SCRIPT RESULT
    # ============================================================

    print("\n========== VALIDATING SCRIPT ==========\n")

    try:
        script_data = json.loads(script_result)

        screenplay = ScreenplayAnalysis.model_validate(
            script_data
        )

        print("✅ ScreenplayAnalysis validation successful.")

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Script Agent returned invalid JSON: {exc}"
        ) from exc

    except Exception as exc:
        raise RuntimeError(
            f"Screenplay schema validation failed: {exc}"
        ) from exc

    # ============================================================
    # STEP 3: BUDGET ANALYSIS
    # ============================================================

    print("\n💰 STEP 2 — Budget Analysis")
    print("------------------------------------")

    screenplay_json = screenplay.model_dump_json(
        indent=2
    )

    budget_prompt = f"""
Create a preliminary production budget using ONLY the
following validated screenplay analysis.

Do not analyze the original screenplay again.

SCREENPLAY ANALYSIS:

{screenplay_json}

Return ONLY the BudgetAnalysis JSON structure.
"""

    budget_message = types.Content(
        role="user",
        parts=[
            types.Part(
                text=budget_prompt
            )
        ],
    )

    budget_result = await run_agent(
        agent=budget_agent,
        message=budget_message,
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=f"{SESSION_ID}-budget",
    )

    print("\n========== BUDGET RESULT ==========\n")
    print(budget_result)

    # ============================================================
    # STEP 4: VALIDATE BUDGET RESULT
    # ============================================================

    print("\n========== VALIDATING BUDGET ==========\n")

    try:
        budget_data = json.loads(budget_result)

        budget = BudgetAnalysis.model_validate(
            budget_data
        )

        print("✅ BudgetAnalysis validation successful.")

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Budget Agent returned invalid JSON: {exc}"
        ) from exc

    except Exception as exc:
        raise RuntimeError(
            f"Budget schema validation failed: {exc}"
        ) from exc

    # ============================================================
    # STEP 5: BUILD PRODUCTION STATE
    # ============================================================

    production_state = ProductionState(
        screenplay_analysis=screenplay,
        budget_analysis=budget,
    )

    print("\n🎬 PRODUCTION STATE")
    print("====================================")

    print(
        f"\nTitle: "
        f"{production_state.screenplay_analysis.title}"
    )

    print(
        f"Scenes: "
        f"{production_state.screenplay_analysis.scene_count}"
    )

    print(
        f"Shoot Days: "
        f"{production_state.screenplay_analysis.estimated_shoot_days}"
    )

    print(
        f"Budget: "
        f"₹{production_state.budget_analysis.total_estimated_cost:,.0f}"
    )

    print(
        "\n✅ CinePilot Script → Budget pipeline completed."
    )


def main():

    if len(sys.argv) != 2:
        print(
            "Usage:\n"
            "python scripts/run_production.py "
            "<screenplay.pdf>"
        )
        sys.exit(1)

    asyncio.run(
        run_production(sys.argv[1])
    )


if __name__ == "__main__":
    main()