import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import asyncio
import os
import sys
import json

from schemas.screenplay import ScreenplayAnalysis
from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agents.director.agent import director_agent


load_dotenv()


APP_NAME = "cinepilot"
USER_ID = "local_user"
SESSION_ID = "screenplay_analysis"


async def analyze_screenplay(pdf_path: str) -> None:
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Screenplay not found: {pdf_path}")

    session_service = InMemorySessionService()

    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )

    runner = Runner(
        agent=director_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    with open(pdf_path, "rb") as file:
        pdf_bytes = file.read()

    user_content = types.Content(
        role="user",
        parts=[
            types.Part(
                text=(
                    "Analyze the attached screenplay PDF. "
                    "Delegate the analysis to the Script Agent."
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

    print("\n🎬 CinePilot AI")
    print("Analyzing screenplay...\n")

    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=SESSION_ID,
        new_message=user_content,
    ):
        if event.is_final_response():
            print("\n========== RAW AGENT RESULT ==========\n")

            if not event.content or not event.content.parts:
                print("No final response received.")
                continue

            text = event.content.parts[0].text

            print(text)

            print("\n========== VALIDATING JSON ==========\n")

            try:
                data = json.loads(text)

                screenplay = ScreenplayAnalysis.model_validate(data)

                print("✅ Screenplay JSON validation successful!")

                print("\n========== VALIDATED RESULT ==========\n")

                print(
                    screenplay.model_dump_json(
                        indent=2
                    )
                )

            except json.JSONDecodeError as exc:
                print("❌ Agent did not return valid JSON.")
                print(f"JSON error: {exc}")

            except Exception as exc:
                print("❌ Screenplay schema validation failed.")
                print(f"Validation error: {exc}")


def main() -> None:
    if len(sys.argv) != 2:
        print(
            "Usage: python scripts/analyze_screenplay.py "
            "<path-to-pdf>"
        )
        sys.exit(1)

    asyncio.run(analyze_screenplay(sys.argv[1]))


if __name__ == "__main__":
    main()