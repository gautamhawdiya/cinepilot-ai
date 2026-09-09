import os
import time
from io import BytesIO
from pathlib import Path

from google import genai
from google.genai.errors import ClientError
from google.genai.types import GenerateContentConfig, Modality
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "storyboards"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_IMAGE_MODEL = "gemini-3.1-flash-image"

# The image model's quota is strict enough that even a handful of
# concurrent requests routinely hit 429 RESOURCE_EXHAUSTED (confirmed:
# firing 16 at once succeeded for only 2). Retry with backoff so a
# transient rate-limit doesn't permanently drop a shot's image.
_MAX_ATTEMPTS = 5
_BASE_DELAY_SECONDS = 3


def _generate_image(prompt: str) -> Image.Image:
    client = genai.Client(
        vertexai=True,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.environ["GOOGLE_CLOUD_LOCATION"],
    )

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = client.models.generate_content(
                model=_IMAGE_MODEL,
                contents=prompt,
                config=GenerateContentConfig(
                    response_modalities=[
                        Modality.TEXT,
                        Modality.IMAGE,
                    ],
                ),
            )
        except ClientError as exc:
            if exc.code == 429 and attempt < _MAX_ATTEMPTS:
                time.sleep(_BASE_DELAY_SECONDS * (2 ** (attempt - 1)))
                continue
            raise

        for part in response.candidates[0].content.parts:
            if part.inline_data:
                return Image.open(BytesIO(part.inline_data.data))

        raise RuntimeError("Gemini returned no image.")

    raise RuntimeError("Gemini image generation exhausted retries.")


def generate_storyboard_image(
    prompt: str,
    scene_number: int,
    shot_number: int,
) -> str:
    """Generate one shot's image into the global (non-project-scoped)
    outputs/storyboards/ directory. Used by the standalone batch-generation
    CLI script, not the live per-project API pipeline.
    """
    image = _generate_image(prompt)
    output_file = (
        OUTPUT_DIR
        / f"scene_{scene_number:02d}_"
          f"shot_{shot_number:02d}.png"
    )
    image.save(output_file)
    return str(output_file)


def generate_scene_image_to_path(prompt: str, output_path: Path) -> Path:
    """Generate one image and save it to an explicit path. Used by the live
    per-project pipeline to write project-scoped storyboard preview images.
    """
    image = _generate_image(prompt)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path
