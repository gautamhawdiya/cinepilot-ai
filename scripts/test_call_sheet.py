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
from schemas.call_sheet import CallSheet

from agents.call_sheet.agent import call_sheet_agent
from validators.call_sheet_validator import assert_call_sheet_production_ready

load_dotenv(PROJECT_ROOT / ".env")


APP_NAME = "cinepilot-call-sheet"
USER_ID = "local_user"
SESSION_ID = "call_sheet_test"


def load_json(filename):

    path = PROJECT_ROOT / "test_data" / filename

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)

def clean_json_response(text: str) -> str:

    text = text.strip()

    if text.startswith("```json"):
        text = text[len("```json"):].strip()

    elif text.startswith("```"):
        text = text[len("```"):].strip()

    if text.endswith("```"):
        text = text[:-3].strip()

    return text


async def main():

    print()
    print("🎬 CinePilot AI - Call Sheet Agent")
    print("=" * 50)

    # ---------------------------------------------------------
    # Load screenplay
    # ---------------------------------------------------------

    screenplay_data = load_json(
        "sample_screenplay_analysis.json"
    )

    screenplay = ScreenplayAnalysis.model_validate(
        screenplay_data
    )

    print()
    print(
        f"Screenplay: {screenplay.title}"
    )

    print(
        f"Scenes: {screenplay.scene_count}"
    )

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
    # Load storyboard
    # ---------------------------------------------------------

    storyboard_path = (
        PROJECT_ROOT
        / "outputs"
        / "storyboards"
        / "storyboard.json"
    )

    if storyboard_path.exists():

        storyboard_data = json.loads(
            storyboard_path.read_text(
                encoding="utf-8"
            )
        )

        storyboard = Storyboard.model_validate(
            storyboard_data
        )

        print(
            f"Storyboard shots: "
            f"{storyboard.total_shots}"
        )

    else:

        print(
            "\n⚠️ storyboard.json not found."
        )

        print(
            "Using empty storyboard."
        )

        storyboard = Storyboard(
            title=screenplay.title,
            visual_style="Not available",
            cinematography_strategy="Not available",
            scenes=[],
            total_shots=0,
        )

    # ---------------------------------------------------------
    # Load production research
    # ---------------------------------------------------------

    research_path = (
        PROJECT_ROOT
        / "outputs"
        / "production"
        / "production_research.json"
    )

    if research_path.exists():

        production_research = json.loads(
            research_path.read_text(
                encoding="utf-8"
            )
        )

        print(
            f"Production research findings: "
            f"{len(production_research.get('findings', []))}"
        )

        print(
            f"Production recommendations: "
            f"{len(production_research.get('production_recommendations', []))}"
        )

    else:

        print(
            "\n⚠️ production_research.json not found."
        )

        print(
            "Using empty production research."
        )

        production_research = {
            "research_topic": "",
            "findings": [],
            "production_recommendations": [],
        }

    # ---------------------------------------------------------
    # Build prompt
    # ---------------------------------------------------------

    prompt = f"""
    Create a production-ready call sheet.

    ============================================================
    SCREENPLAY ANALYSIS
    ============================================================

    {screenplay.model_dump_json(indent=2)}

    ============================================================
    PRODUCTION PLAN
    ============================================================

    {production_plan.model_dump_json(indent=2)}

    ============================================================
    STORYBOARD
    ============================================================

    {storyboard.model_dump_json(indent=2)}

    ============================================================
    PRODUCTION RESEARCH
    ============================================================

    {json.dumps(
        production_research,
        indent=2,
        ensure_ascii=False,
    )}

    ============================================================
    FINAL REQUIREMENTS
    ============================================================

    Create the call sheet using ONLY the supplied information.

    The output must be a CallSheet object.

    Do not use a wrapper object.

    Do not use:

    call_sheet
    call_sheets
    project_info
    shoot_day
    scenes
    cast
    crew
    props
    equipment

    Use the exact field names defined by the CallSheet schema.

    The production research is advisory.

    If research contains:

    "requires_local_verification": true

    convert it into a verification requirement rather
    than presenting it as a universal confirmed rule.

    Never invent:

    - calendar dates
    - exact station
    - railway operator
    - permit fees
    - insurance amount
    - named actors
    - named crew
    - production company

    If information is unavailable, use null or TBD
    according to the CallSheet schema.

    Every shoot day must contain at least one
    scenes_scheduled item.

    Every screenplay scene that is scheduled must use
    its real scene number and heading.

    Return ONLY the CallSheet JSON object.
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
        agent=call_sheet_agent,
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

    print()
    print(
        "📋 Generating production call sheet..."
    )

    final_text = None

    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=SESSION_ID,
        new_message=message,
    ):

        if event.is_final_response():

            if (
                event.content
                and event.content.parts
            ):

                for part in event.content.parts:

                    if part.text:

                        final_text = part.text

                        break

    if not final_text:

        raise RuntimeError(
            "Call Sheet Agent returned no response."
        )

    # ---------------------------------------------------------
    # Raw result
    # ---------------------------------------------------------

    print()
    print(
        "========== RAW CALL SHEET =========="
    )

    print(final_text)

    # ---------------------------------------------------------
    # Validate
    # ---------------------------------------------------------

    print()
    print(
        "========== VALIDATING CALL SHEET =========="
    )

    try:

        cleaned_text = clean_json_response(
            final_text
        )

        call_sheet = CallSheet.model_validate_json(
            cleaned_text
        )

        print()
        print(
            "========== PRODUCTION QUALITY VALIDATION =========="
        )

        assert_call_sheet_production_ready(
            call_sheet
        )

        print(
            "✅ Production quality validation successful!"
        )

        # ---------------------------------------------------------
        # Structural completeness checks
        # ---------------------------------------------------------

        if not call_sheet.shoot_days:
            raise RuntimeError(
                "Call Sheet validation passed, but "
                "NO SHOOT DAYS were generated."
            )

        if call_sheet.shoot_days_total != len(
            call_sheet.shoot_days
        ):
            raise RuntimeError(
                "Call Sheet shoot_days_total does not "
                "match the number of shoot_days."
            )

        total_scenes = sum(
            len(day.scenes_scheduled)
            for day in call_sheet.shoot_days
        )

        if total_scenes == 0:
            raise RuntimeError(
                "Call Sheet contains shoot days but "
                "NO SCHEDULED SCENES."
            )

        print(
            f"Validated shoot days: "
            f"{len(call_sheet.shoot_days)}"
        )

        print(
            f"Validated scenes: "
            f"{total_scenes}"
        )

    except Exception as exc:

        print(
            "❌ Call Sheet validation failed:"
        )

        print(exc)

        raise

    print(
        "✅ Call Sheet validation successful!"
    )

    # ---------------------------------------------------------
    # Save
    # ---------------------------------------------------------

    output_dir = (
        PROJECT_ROOT
        / "outputs"
        / "production"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = (
        output_dir
        / "call_sheet.json"
    )

    output_file.write_text(
        call_sheet.model_dump_json(
            indent=2
        ),
        encoding="utf-8",
    )

    # ---------------------------------------------------------
    # Validated output
    # ---------------------------------------------------------

    print()
    print(
        "========== VALIDATED CALL SHEET =========="
    )

    print(
        call_sheet.model_dump_json(
            indent=2
        )
    )

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------

    print("\n" + "=" * 50)
    print("CALL SHEET SUMMARY")
    print("=" * 50)

    print(f"Project: {call_sheet.project_title}")
    print(f"Total Shoot Days: {call_sheet.shoot_days_total}")

    for day in call_sheet.shoot_days:

        print("\n" + "-" * 50)

        print(
            f"Shoot Day: {day.day_number}"
        )

        print(
            f"Location: {day.location}"
        )

        print(
            f"Crew Call: {day.crew_call}"
        )

        print(
            f"First Shot: {day.first_shot}"
        )

        print(
            f"Lunch Break: {day.lunch_break}"
        )

        print(
            f"Wrap: {day.wrap}"
        )

        print(
            f"Scenes: "
            f"{len(day.scenes_scheduled)}"
        )

        print(
            f"Cast: "
            f"{len(day.cast_on_call)}"
        )

        print(
            f"Crew: "
            f"{len(day.crew_on_call)}"
        )

        print(
            f"Equipment: "
            f"{len(day.required_equipment)}"
        )

        print(
            f"Production Notes: "
            f"{len(day.production_notes)}"
        )

        print(
            f"Safety Items: "
            f"{len(day.safety_and_logistics)}"
        )

    print("\n" + "=" * 50)
    print("CALL SHEET VALIDATION COMPLETE")
    print("=" * 50)
    print()
    print(
        f"💾 Call sheet saved:"
        f"\n{output_file}"
    )


if __name__ == "__main__":

    asyncio.run(main())