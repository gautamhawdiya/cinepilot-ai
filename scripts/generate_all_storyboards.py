import sys
from pathlib import Path
import json
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

from schemas.storyboard import Storyboard
from tools.image_generation import generate_storyboard_image


load_dotenv(PROJECT_ROOT / ".env")


STORYBOARD_FILE = (
    PROJECT_ROOT
    / "outputs"
    / "storyboards"
    / "storyboard.json"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "storyboards"
)


def load_storyboard():

    if not STORYBOARD_FILE.exists():

        raise FileNotFoundError(
            f"Storyboard file not found:\n"
            f"{STORYBOARD_FILE}\n\n"
            f"Run generate_storyboard.py first."
        )

    data = json.loads(
        STORYBOARD_FILE.read_text(
            encoding="utf-8"
        )
    )

    return Storyboard.model_validate(data)


def main():

    print()
    print("🎬 CinePilot AI")
    print("🎞️ Batch Storyboard Image Generator")
    print("=" * 60)

    # ---------------------------------------------------------
    # Load storyboard
    # ---------------------------------------------------------

    storyboard = load_storyboard()

    print(
        f"\nProject: {storyboard.title}"
    )

    print(
        f"Scenes: {len(storyboard.scenes)}"
    )

    print(
        f"Total shots: {storyboard.total_shots}"
    )

    generated = 0
    skipped = 0
    failed = 0

    # ---------------------------------------------------------
    # Process scenes
    # ---------------------------------------------------------

    for scene in storyboard.scenes:

        print()
        print(
            f"🎬 Scene {scene.scene_number}: "
            f"{scene.scene_heading}"
        )

        for shot in scene.shots:

            output_file = (
                OUTPUT_DIR
                / (
                    f"scene_{scene.scene_number:02d}_"
                    f"shot_{shot.shot_number:02d}.png"
                )
            )

            # -------------------------------------------------
            # Resume-safe check
            # -------------------------------------------------

            if output_file.exists():

                print(
                    f"⏭️ Shot {shot.shot_number}: "
                    f"already exists — skipping"
                )

                skipped += 1

                continue

            # -------------------------------------------------
            # Generate
            # -------------------------------------------------

            print()
            print(
                f"🖼️ Shot {shot.shot_number}: "
                f"generating..."
            )

            print(
                f"   VFX: "
                f"{'YES' if shot.vfx_required else 'NO'}"
            )

            try:

                generate_storyboard_image(
                    prompt=shot.image_prompt,
                    scene_number=scene.scene_number,
                    shot_number=shot.shot_number,
                )

                print(
                    f"   ✅ Shot {shot.shot_number} complete"
                )

                generated += 1

            except Exception as exc:

                error_text = str(exc)

                if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:

                    print(
                        "\n🛑 Gemini image-generation quota exhausted."
                    )

                    print(
                        "Stopping batch generation to avoid "
                        "repeated quota failures."
                    )

                    print(
                        f"Shots generated so far: {generated}"
                    )

                    print(
                        f"Shots skipped: {skipped}"
                    )

                    print(
                        f"Shots failed due to quota: "
                        f"{failed + 1}"
                    )

                    print(
                        "\nRun this script again later."
                    )

                    return

                print(
                    f"   ❌ Shot {shot.shot_number} failed"
                )

                print(
                    f"   Error: {exc}"
                )

                failed += 1

            # -------------------------------------------------
            # Small delay between requests
            # -------------------------------------------------

            time.sleep(1)

    # ---------------------------------------------------------
    # Final summary
    # ---------------------------------------------------------

    print()
    print("=" * 60)
    print("🎬 STORYBOARD GENERATION COMPLETE")
    print("=" * 60)

    print(
        f"Generated : {generated}"
    )

    print(
        f"Skipped   : {skipped}"
    )

    print(
        f"Failed    : {failed}"
    )

    print(
        f"Expected  : {storyboard.total_shots}"
    )

    print()
    print(
        f"Output directory:\n"
        f"{OUTPUT_DIR}"
    )


if __name__ == "__main__":
    main()