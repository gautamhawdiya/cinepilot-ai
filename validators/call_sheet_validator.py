from schemas.call_sheet import CallSheet


class CallSheetValidationError(Exception):
    """Raised when a call sheet is structurally valid
    but not production-ready."""
    pass


def validate_call_sheet_quality(
    call_sheet: CallSheet,
) -> list[str]:

    errors: list[str] = []

    # ---------------------------------------------------------
    # Basic project validation
    # ---------------------------------------------------------

    if not call_sheet.project_title:
        errors.append(
            "Project title is missing."
        )

    if not call_sheet.shoot_days:
        errors.append(
            "No shoot days were generated."
        )

    # ---------------------------------------------------------
    # Shoot-day count
    # ---------------------------------------------------------

    actual_days = len(
        call_sheet.shoot_days
    )

    if call_sheet.shoot_days_total != actual_days:

        errors.append(
            f"shoot_days_total={call_sheet.shoot_days_total} "
            f"but actual shoot days={actual_days}."
        )

    # ---------------------------------------------------------
    # Shoot-day numbering
    # ---------------------------------------------------------

    expected_day_numbers = list(
        range(1, actual_days + 1)
    )

    actual_day_numbers = [
        day.day_number
        for day in call_sheet.shoot_days
    ]

    if actual_day_numbers != expected_day_numbers:

        errors.append(
            "Shoot day numbering is invalid. "
            f"Expected {expected_day_numbers}, "
            f"got {actual_day_numbers}."
        )

    # ---------------------------------------------------------
    # Validate each shoot day
    # ---------------------------------------------------------

    all_scene_numbers: list[int] = []

    for day in call_sheet.shoot_days:

        prefix = (
            f"Shoot Day {day.day_number}"
        )

        # Location
        if not day.location.strip():
            errors.append(
                f"{prefix}: location is missing."
            )

        # Schedule
        if not day.crew_call:
            errors.append(
                f"{prefix}: crew call is missing."
            )

        if not day.first_shot:
            errors.append(
                f"{prefix}: first shot is missing."
            )

        if not day.lunch_break:
            errors.append(
                f"{prefix}: lunch break is missing."
            )

        if not day.wrap:
            errors.append(
                f"{prefix}: wrap time is missing."
            )

        # Scenes
        if not day.scenes_scheduled:

            errors.append(
                f"{prefix}: no scenes scheduled."
            )

        # -----------------------------------------------------
        # Validate scenes
        # -----------------------------------------------------

        for scene in day.scenes_scheduled:

            if scene.scene_number in all_scene_numbers:

                errors.append(
                    f"Scene {scene.scene_number} "
                    "is scheduled more than once."
                )

            all_scene_numbers.append(
                scene.scene_number
            )

            if not scene.heading.strip():

                errors.append(
                    f"Scene {scene.scene_number}: "
                    "heading is missing."
                )

            if not scene.summary.strip():

                errors.append(
                    f"Scene {scene.scene_number}: "
                    "summary is missing."
                )

    # ---------------------------------------------------------
    # Cast validation
    # ---------------------------------------------------------

    cast_characters = set()

    for cast in call_sheet.cast_list:

        character = (
            cast.character_name.strip()
        )

        if not character:
            errors.append(
                "Cast list contains an empty character."
            )
            continue

        normalized = character.upper()

        if normalized in cast_characters:

            errors.append(
                f"Duplicate cast character: "
                f"{character}."
            )

        cast_characters.add(
            normalized
        )

    # ---------------------------------------------------------
    # Crew validation
    # ---------------------------------------------------------

    crew_roles = set()

    for crew in call_sheet.crew_list:

        role = crew.role.strip()

        if not role:

            errors.append(
                "Crew list contains an empty role."
            )
            continue

        normalized = role.upper()

        if normalized in crew_roles:

            errors.append(
                f"Duplicate crew role: "
                f"{role}."
            )

        crew_roles.add(
            normalized
        )

    # ---------------------------------------------------------
    # Detect obviously empty production data
    # ---------------------------------------------------------

    if (
        actual_days > 0
        and not call_sheet.cast_list
        and not call_sheet.crew_list
    ):

        errors.append(
            "Call sheet contains shoot days but "
            "both cast_list and crew_list are empty."
        )

    return errors


def assert_call_sheet_production_ready(
    call_sheet: CallSheet,
) -> None:

    errors = validate_call_sheet_quality(
        call_sheet
    )

    if errors:

        message = (
            "\nCall Sheet production validation failed:\n"
            + "\n".join(
                f"  ❌ {error}"
                for error in errors
            )
        )

        raise CallSheetValidationError(
            message
        )