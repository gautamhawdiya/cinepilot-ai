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
from schemas.production_plan import ProductionPlan
from schemas.storyboard import Storyboard

from agents.storyboard.agent import storyboard_agent


load_dotenv(PROJECT_ROOT / ".env")


APP_NAME = "cinepilot-storyboard"
USER_ID = "local_user"
SESSION_ID = "storyboard_test"


def load_json(filename):
    path = PROJECT_ROOT / "test_data" / filename

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


async def main():

    print("\n🎬 CinePilot AI - Storyboard Agent")
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
    print(
        f"Shoot Days: "
        f"{screenplay.estimated_shoot_days}"
    )

    # ---------------------------------------------------------
    # Load production plan
    # ---------------------------------------------------------

    production_plan_data = load_json(
        "sample_production_plan.json"
    )

    production_plan = ProductionPlan.model_validate(
        production_plan_data
    )

    print(
        f"Production confidence: "
        f"{production_plan.confidence}"
    )

    # ---------------------------------------------------------
    # Build prompt
    # ---------------------------------------------------------

    prompt = f"""
Create a cinematic storyboard for this screenplay.

SCREENPLAY ANALYSIS:

{screenplay.model_dump_json(indent=2)}


PRODUCTION PLAN:

{production_plan.model_dump_json(indent=2)}


Create practical, production-ready shots.

Important:

- Stay faithful to the screenplay.
- Use the production plan constraints.
- Identify VFX shots.
- Do not invent major story events.
- Generate detailed image prompts.
- Make the visual language cinematic and consistent.
- Return ONLY valid JSON matching the Storyboard schema.
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
        agent=storyboard_agent,
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
    # Execute
    # ---------------------------------------------------------

    print("\n🎥 Generating cinematic storyboard...")

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
            "Storyboard Agent returned no response."
        )

    # ---------------------------------------------------------
    # Raw result
    # ---------------------------------------------------------

    print(
        "\n========== RAW STORYBOARD ==========\n"
    )

    print(final_text)

    # ---------------------------------------------------------
    # Validate
    # ---------------------------------------------------------

    print(
        "\n========== VALIDATING STORYBOARD ==========\n"
    )

    try:

        storyboard = Storyboard.model_validate_json(
            final_text
        )

    except Exception as exc:

        print(
            "❌ Storyboard validation failed:"
        )

        print(exc)

        raise

    print(
        "✅ Storyboard validation successful!"
    )

    # ---------------------------------------------------------
    # Validated output
    # ---------------------------------------------------------

    print(
        "\n========== VALIDATED STORYBOARD ==========\n"
    )

    print(
        storyboard.model_dump_json(
            indent=2
        )
    )

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------

    print(
        "\n========================================"
    )

    print(
        f"Scenes storyboarded: "
        f"{len(storyboard.scenes)}"
    )

    print(
        f"Total shots: "
        f"{storyboard.total_shots}"
    )


if __name__ == "__main__":
    asyncio.run(main())