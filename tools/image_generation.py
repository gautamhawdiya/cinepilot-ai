import os
from io import BytesIO
from pathlib import Path

from google import genai
from google.genai.types import GenerateContentConfig, Modality
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "storyboards"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_storyboard_image(
    prompt: str,
    scene_number: int,
    shot_number: int,
) -> str:

    client = genai.Client(
        vertexai=True,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.environ["GOOGLE_CLOUD_LOCATION"],
    )

    response = client.models.generate_content(
        model="gemini-3.1-flash-image",
        contents=prompt,
        config=GenerateContentConfig(
            response_modalities=[
                Modality.TEXT,
                Modality.IMAGE,
            ],
        ),
    )

    for part in response.candidates[0].content.parts:

        if part.inline_data:
            image = Image.open(
                BytesIO(part.inline_data.data)
            )

            output_file = (
                OUTPUT_DIR
                / f"scene_{scene_number:02d}_"
                  f"shot_{shot_number:02d}.png"
            )

            image.save(output_file)

            return str(output_file)

    raise RuntimeError(
        "Gemini returned no image."
    )