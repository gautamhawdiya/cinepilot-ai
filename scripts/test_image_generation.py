import sys
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")


from tools.image_generation import generate_storyboard_image


def main():

    print()
    print("🎬 CinePilot AI")
    print("🖼️ First Storyboard Image")
    print("=" * 50)

    prompt = """
Create a cinematic storyboard frame for a science-fiction
mystery short film.

MAYA SEN, a 27-year-old freelance filmmaker, is alone in
her modest apartment at night.

She sits near a desk surrounded by three computer monitors.
An old digital camera rests on the desk.

Rain is visible through the apartment window.

Maya has just noticed that the old digital camera has
mysteriously turned on. She looks toward it with cautious
curiosity.

The scene should feel tense, mysterious and grounded,
like a professionally photographed science-fiction
thriller.

Cinematic 35mm composition.
Medium-wide shot.
Realistic Indian apartment interior.
Nighttime practical lighting.
Subtle cool nighttime atmosphere.
Natural skin tones.
Shallow depth of field.
Professional film cinematography.

Do not show any supernatural creature.
Do not show future footage.
Do not show a train.
Do not add characters.
No subtitles.
No watermark.
No logos.
"""

    print("Generating...")

    output = generate_storyboard_image(
        prompt=prompt,
        scene_number=1,
        shot_number=1,
    )

    print()
    print("✅ IMAGE GENERATED")
    print()
    print(f"Output: {output}")


if __name__ == "__main__":
    main()