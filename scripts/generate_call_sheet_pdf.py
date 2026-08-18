import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.call_sheet import CallSheet
from pdf.call_sheet_pdf import generate_call_sheet_pdf


def main():

    print()
    print("🎬 CinePilot AI")
    print("📄 Call Sheet PDF Generator")
    print("=" * 55)

    # ---------------------------------------------------------
    # Load validated call sheet
    # ---------------------------------------------------------

    json_path = (
        PROJECT_ROOT
        / "outputs"
        / "production"
        / "call_sheet.json"
    )

    if not json_path.exists():
        raise FileNotFoundError(
            f"Call sheet JSON not found:\n{json_path}"
        )

    print()
    print("📋 Loading validated call sheet...")
    print(json_path)

    call_sheet_data = json.loads(
        json_path.read_text(
            encoding="utf-8"
        )
    )

    # ---------------------------------------------------------
    # Validate AGAIN before rendering
    # ---------------------------------------------------------

    print()
    print("🔍 Validating call sheet...")

    call_sheet = CallSheet.model_validate(
        call_sheet_data
    )

    print("✅ Call sheet validation successful")

    # ---------------------------------------------------------
    # Generate PDF
    # ---------------------------------------------------------

    output_path = (
        PROJECT_ROOT
        / "outputs"
        / "production"
        / "call_sheet.pdf"
    )

    print()
    print("📄 Generating PDF...")

    generate_call_sheet_pdf(
        call_sheet=call_sheet,
        output_path=output_path,
    )

    print()
    print("=" * 55)
    print("✅ CALL SHEET PDF GENERATED")
    print("=" * 55)

    print()
    print(f"Output:")
    print(output_path)
    print()


if __name__ == "__main__":
    main()