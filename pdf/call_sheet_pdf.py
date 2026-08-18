from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
)

from schemas.call_sheet import CallSheet


PAGE_W, PAGE_H = A4
MARGIN_X = 15 * mm
CONTENT_W = PAGE_W - (2 * MARGIN_X)


def text(value, default="TBD"):
    if value is None:
        return default
    value = str(value).strip()
    return value if value else default


def esc(value, default="TBD"):
    return (
        text(value, default)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def styles():
    base = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=22, leading=25, alignment=TA_CENTER, spaceAfter=3
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"], fontName="Helvetica",
            fontSize=9.5, leading=12, alignment=TA_CENTER, spaceAfter=9
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontName="Helvetica-Bold",
            fontSize=15, leading=18, spaceAfter=6
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=10.5, leading=13, spaceBefore=6, spaceAfter=4
        ),
        "h3": ParagraphStyle(
            "h3", parent=base["Heading3"], fontName="Helvetica-Bold",
            fontSize=8.8, leading=11, spaceBefore=3, spaceAfter=2
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"], fontName="Helvetica",
            fontSize=7.7, leading=9.7, spaceAfter=1.5
        ),
        "small": ParagraphStyle(
            "small", parent=base["BodyText"], fontName="Helvetica",
            fontSize=6.9, leading=8.5
        ),
        "label": ParagraphStyle(
            "label", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=7.1, leading=8.5
        ),
        "th": ParagraphStyle(
            "th", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=7.1, leading=8.5
        ),
        "big_call": ParagraphStyle(
            "big_call", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=9.2, leading=11, alignment=TA_CENTER
        ),
        "call_label": ParagraphStyle(
            "call_label", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=6.2, leading=7.2, alignment=TA_CENTER
        ),
    }


def P(value, style, default="TBD"):
    return Paragraph(esc(value, default), style)


def footer(canvas, document):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#cccccc"))
    canvas.setLineWidth(0.35)
    canvas.line(MARGIN_X, 11 * mm, PAGE_W - MARGIN_X, 11 * mm)
    canvas.setFont("Helvetica", 6.5)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawString(
        MARGIN_X, 6.5 * mm, "CinePilot AI — Production Call Sheet"
    )
    canvas.drawRightString(
        PAGE_W - MARGIN_X, 6.5 * mm, f"Page {document.page}"
    )
    canvas.restoreState()


def section(title, s):
    return Paragraph(title, s["h2"])


def box_table(data, widths, repeat_rows=0, header=True):
    t = Table(data, colWidths=widths, repeatRows=repeat_rows)
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#aaaaaa")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        commands.append(
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8"))
        )
    t.setStyle(TableStyle(commands))
    return t


def call_bar(day, s):
    values = [
        ("LOCATION", day.location),
        ("CREW CALL", day.crew_call),
        ("FIRST SHOT", day.first_shot),
        ("LUNCH", day.lunch_break),
        ("WRAP", day.wrap),
    ]

    data = [
        [P(label, s["call_label"]) for label, _ in values],
        [P(value, s["big_call"]) for _, value in values],
    ]

    return box_table(
        data,
        [CONTENT_W / 5] * 5,
        header=False,
    )


def day_banner(day, s):
    t = Table(
        [[Paragraph(f"SHOOT DAY {day.day_number}", s["h1"])]],
        colWidths=[CONTENT_W],
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#222222")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def scene_block(scene, s):
    out = [
        Paragraph(
            f"SCENE {scene.scene_number} — {esc(scene.heading)}",
            s["h3"]
        ),
        Paragraph(
            f"<b>Summary:</b> {esc(scene.summary)}",
            s["body"]
        ),
        Paragraph(
            f"<b>Estimated Shooting Time:</b> "
            f"{esc(scene.estimated_shooting_time)}",
            s["body"]
        ),
        Paragraph(
            f"<b>Characters:</b> "
            f"{esc(', '.join(scene.characters_present) or 'None')}",
            s["body"]
        ),
        Paragraph(
            f"<b>Props:</b> "
            f"{esc(', '.join(scene.props) or 'None')}",
            s["body"]
        ),
    ]

    if scene.vfx_requirements:
        out.append(
            Paragraph(
                f"<b>VFX:</b> "
                f"{esc('; '.join(scene.vfx_requirements))}",
                s["body"]
            )
        )

    if scene.notes:
        out.append(
            Paragraph(
                f"<b>Notes:</b> {esc(scene.notes)}",
                s["body"]
            )
        )

    return KeepTogether(out)


def people_tables(day, s):
    cast = [
        [P("CAST ON CALL", s["th"])]
    ]
    for item in day.cast_on_call or ["None"]:
        cast.append([P(f"• {item}", s["body"])])

    crew = [
        [P("CREW ON CALL", s["th"])]
    ]
    for item in day.crew_on_call or ["None"]:
        crew.append([P(f"• {item}", s["body"])])

    ct = box_table(cast, [CONTENT_W / 2 - 2], header=True)
    wt = box_table(crew, [CONTENT_W / 2 - 2], header=True)

    wrapper = Table(
        [[ct, wt]],
        colWidths=[CONTENT_W / 2, CONTENT_W / 2],
    )
    wrapper.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return wrapper


def list_box(title, items, s):
    rows = [[P(title, s["th"])]]
    for item in items or ["None"]:
        rows.append([P(f"• {item}", s["body"])])

    return box_table(rows, [CONTENT_W], header=True)


def render_day_core(day, s):
    story = [
        day_banner(day, s),
        Spacer(1, 4),
        call_bar(day, s),
        Spacer(1, 5),
        section("SCENES", s),
    ]

    for scene in day.scenes_scheduled:
        story.append(scene_block(scene, s))

    story += [
        Spacer(1, 5),
        people_tables(day, s),
    ]

    return story


def render_resources(day, s):
    story = [
        section(f"DAY {day.day_number} — PRODUCTION RESOURCES", s),
        list_box("REQUIRED PROPS", day.required_props, s),
        Spacer(1, 5),
        list_box("REQUIRED EQUIPMENT", day.required_equipment, s),
        Spacer(1, 5),
        list_box("PRODUCTION NOTES", day.production_notes, s),
        Spacer(1, 5),
        list_box("SAFETY & LOGISTICS", day.safety_and_logistics, s),
    ]
    return story


def generate_call_sheet_pdf(call_sheet: CallSheet, output_path: Path):
    """
    V3 layout only.

    No changes to:
      - CallSheet schema
      - Call Sheet Agent
      - screenplay analysis
      - production plan
      - storyboard
      - research

    Layout:
      Page 1: production overview + both day summaries
      Page 2: Day 1 scenes/cast/crew
      Page 3: Day 1 resources + Day 2 quick overview
      Page 4: Day 2 scenes/cast/crew + resources
      Page 5: master cast/crew
    """

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    s = styles()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=MARGIN_X,
        leftMargin=MARGIN_X,
        topMargin=13 * mm,
        bottomMargin=16 * mm,
        title=f"{call_sheet.project_title} - Production Call Sheet",
        author="CinePilot AI",
    )

    story = []
    days = call_sheet.shoot_days

    # ========================================================
    # PAGE 1 — OVERVIEW
    # ========================================================

    story += [
        Paragraph(esc(call_sheet.project_title), s["title"]),
        Paragraph("PRODUCTION CALL SHEET", s["subtitle"]),
        section("PRODUCTION INFORMATION", s),
    ]

    production_rows = [
        [P("Call Sheet ID", s["label"]), P(call_sheet.call_sheet_id, s["body"])],
        [P("Production Company", s["label"]),
         P(call_sheet.production_company, s["body"])],
        [P("Project Manager", s["label"]),
         P(call_sheet.project_manager, s["body"])],
        [P("Date", s["label"]), P(call_sheet.date, s["body"])],
        [P("Total Shoot Days", s["label"]),
         P(call_sheet.shoot_days_total, s["body"])],
    ]

    story.append(box_table(
        production_rows,
        [42 * mm, CONTENT_W - 42 * mm],
        header=False,
    ))

    logline = getattr(call_sheet, "logline", None)
    if logline:
        story += [
            Spacer(1, 6),
            section("LOGLINE", s),
            Paragraph(esc(logline), s["body"]),
        ]

    story += [
        Spacer(1, 6),
        section("SHOOT DAY OVERVIEW", s),
    ]

    overview = [[
        P("DAY", s["th"]),
        P("DATE", s["th"]),
        P("LOCATION", s["th"]),
        P("CREW CALL", s["th"]),
        P("FIRST SHOT", s["th"]),
        P("LUNCH", s["th"]),
        P("WRAP", s["th"]),
    ]]

    for day in days:
        overview.append([
            P(f"Day {day.day_number}", s["body"]),
            P(day.date, s["body"]),
            P(day.location, s["body"]),
            P(day.crew_call, s["body"]),
            P(day.first_shot, s["body"]),
            P(day.lunch_break, s["body"]),
            P(day.wrap, s["body"]),
        ])

    story.append(box_table(
        overview,
        [
            15 * mm, 23 * mm, 38 * mm, 21 * mm,
            21 * mm, 27 * mm, 21 * mm
        ],
        repeat_rows=1,
    ))

    story += [
        Spacer(1, 8),
        section("CAST OVERVIEW", s),
    ]

    cast_overview = []
    for cast in call_sheet.cast_list:
        cast_overview.append(
            Paragraph(
                f"<b>{esc(cast.character_name)}</b> — "
                f"{esc(cast.actor_name)}",
                s["body"]
            )
        )

    if cast_overview:
        cast_grid = Table(
            [[item] for item in cast_overview],
            colWidths=[CONTENT_W],
        )
        cast_grid.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.35, colors.HexColor("#aaaaaa")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25,
             colors.HexColor("#dddddd")),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(cast_grid)

    story += [Spacer(1, 6), section("DAY QUICK CALLS", s)]

    quick = []
    for day in days:
        quick.append([
            P(f"DAY {day.day_number}", s["th"]),
            P(day.location, s["body"]),
            P(f"Crew {text(day.crew_call)}", s["small"]),
            P(f"Shot {text(day.first_shot)}", s["small"]),
            P(f"Lunch {text(day.lunch_break)}", s["small"]),
            P(f"Wrap {text(day.wrap)}", s["small"]),
        ])

    if quick:
        story.append(box_table(
            quick,
            [22 * mm, 42 * mm, 24 * mm, 24 * mm, 34 * mm, 27 * mm],
            header=False,
        ))

    # ========================================================
    # PAGE 2 — DAY 1 CORE
    # ========================================================

    if days:
        story.append(PageBreak())
        story.extend(render_day_core(days[0], s))

    # ========================================================
    # PAGE 3 — DAY 1 RESOURCES + DAY 2 QUICK OVERVIEW
    # ========================================================

    if days:
        story.append(PageBreak())

        story += render_resources(days[0], s)

        if len(days) > 1:
            story += [
                Spacer(1, 8),
                section("NEXT SHOOT DAY", s),
                day_banner(days[1], s),
                Spacer(1, 4),
                call_bar(days[1], s),
                Spacer(1, 5),
                Paragraph(
                    f"<b>Scenes scheduled:</b> "
                    f"{len(days[1].scenes_scheduled)}",
                    s["body"]
                ),
                Paragraph(
                    f"<b>Location:</b> {esc(days[1].location)}",
                    s["body"]
                ),
            ]

    # ========================================================
    # PAGE 4 — DAY 2 CORE + RESOURCES
    # ========================================================

    if len(days) > 1:
        story.append(PageBreak())
        story.extend(render_day_core(days[1], s))

        story += [
            Spacer(1, 7),
            section("PRODUCTION RESOURCES", s),
        ]

        # Put compact resource lists below the core.
        story.append(
            list_box(
                "PROPS",
                days[1].required_props,
                s
            )
        )
        story.append(Spacer(1, 4))
        story.append(
            list_box(
                "EQUIPMENT",
                days[1].required_equipment,
                s
            )
        )

    # ========================================================
    # PAGE 5 — DAY 2 NOTES + MASTER CAST / CREW
    # ========================================================

    story.append(PageBreak())

    if len(days) > 1:
        story += [
            section("DAY 2 — PRODUCTION NOTES & SAFETY", s),
            list_box(
                "PRODUCTION NOTES",
                days[1].production_notes,
                s
            ),
            Spacer(1, 5),
            list_box(
                "SAFETY & LOGISTICS",
                days[1].safety_and_logistics,
                s
            ),
            Spacer(1, 7),
        ]

    story.append(
        Paragraph("MASTER CAST & CREW", s["h1"])
    )

    story.append(
        section("MASTER CAST", s)
    )

    cast_rows = [[
        P("CHARACTER", s["th"]),
        P("ACTOR", s["th"]),
    ]]

    for cast in call_sheet.cast_list:
        cast_rows.append([
            P(cast.character_name, s["body"]),
            P(cast.actor_name, s["body"]),
        ])

    story.append(
        box_table(
            cast_rows,
            [CONTENT_W / 2, CONTENT_W / 2],
            repeat_rows=1,
        )
    )

    story += [
        Spacer(1, 7),
        section("MASTER CREW", s),
    ]

    crew_rows = [[
        P("ROLE", s["th"]),
        P("NAME", s["th"]),
    ]]

    for crew in call_sheet.crew_list:
        crew_rows.append([
            P(crew.role, s["body"]),
            P(crew.name, s["body"]),
        ])

    story.append(
        box_table(
            crew_rows,
            [CONTENT_W / 2, CONTENT_W / 2],
            repeat_rows=1,
        )
    )

    doc.build(
        story,
        onFirstPage=footer,
        onLaterPages=footer,
    )


# Optional CLI-compatible entry point.
if __name__ == "__main__":
    import json
    import sys

    project_root = Path(__file__).resolve().parent.parent
    input_file = (
        project_root / "outputs" / "production" / "call_sheet.json"
    )
    output_file = (
        project_root / "outputs" / "production" / "call_sheet.pdf"
    )

    if not input_file.exists():
        raise FileNotFoundError(
            f"Call sheet JSON not found: {input_file}"
        )

    data = json.loads(
        input_file.read_text(encoding="utf-8")
    )

    call_sheet = CallSheet.model_validate(data)

    generate_call_sheet_pdf(
        call_sheet,
        output_file,
    )

    print(f"✅ Call sheet PDF generated:")
    print(output_file)