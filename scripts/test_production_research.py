import sys
from pathlib import Path
import asyncio
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from dotenv import load_dotenv

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agents.production_research.agent import (
    production_research_agent,
)


load_dotenv(
    PROJECT_ROOT / ".env"
)


APP_NAME = "cinepilot-production-research"
USER_ID = "local_user"
SESSION_ID = "production_research_test"


async def main():

    print()
    print("🎬 CinePilot AI")
    print("🔎 Production Research Agent")
    print("=" * 60)

    prompt = """
Research production requirements for this screenplay scenario.

PROJECT:
THE LAST FRAME

RELEVANT SCENE:

Scene 4:
INT. TRAIN STATION - NIGHT

Maya confronts the future shown by the camera
at a train station.

PRODUCTION REQUIREMENT:

The production needs to understand practical
filming considerations for train stations.

Research:

- filming permits
- station access
- filming hours
- crew restrictions
- equipment restrictions
- insurance requirements
- safety requirements
- public access considerations

IMPORTANT:

Do not assume a specific train station location
because the screenplay does not provide one.

Research general examples from real railway,
transit, and film authorities.

Clearly identify information that requires
local verification.

Return only valid JSON matching your instructions.
"""

    session_service = InMemorySessionService()

    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )

    runner = Runner(
        agent=production_research_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    message = types.Content(
        role="user",
        parts=[
            types.Part(
                text=prompt
            )
        ],
    )

    print()
    print(
        "🔎 Researching production constraints..."
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
            "Production Research Agent "
            "returned no response."
        )

    print()
    print(
        "========== RAW RESEARCH =========="
    )

    print(final_text)

    print()
    print(
        "========== VALIDATING JSON =========="
    )

    cleaned = final_text.strip()

    if cleaned.startswith("```json"):
        cleaned = cleaned[
            len("```json"):
        ].strip()

    elif cleaned.startswith("```"):
        cleaned = cleaned[
            len("```"):
        ].strip()

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    research = json.loads(
        cleaned
    )

    # ---------------------------------------------------------
    # Save production research
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

    research_file = (
        output_dir
        / "production_research.json"
    )

    research_file.write_text(
        json.dumps(
            research,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print(
        "💾 Production research saved:"
    )
    print(
        research_file
    )

    print(
        "✅ Research JSON is valid."
    )

    print()
    print(
        "Findings:",
        len(
            research.get(
                "findings",
                [],
            )
        ),
    )

    print(
        "Recommendations:",
        len(
            research.get(
                "production_recommendations",
                [],
            )
        ),
    )

    print()
    print("=" * 60)
    print(
        "✅ PRODUCTION RESEARCH AGENT TEST COMPLETE"
    )
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())