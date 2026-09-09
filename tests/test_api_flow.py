"""End-to-end coverage of the project API: upload -> run -> poll -> outputs.

Real Gemini/ADK and Parallel calls are replaced with a fake `Runner` whose
`run_async` yields scripted events -- the one seam where
`api.services.pipeline` talks to ADK. Everything downstream of that seam --
Pydantic validation, project state transitions, file persistence, the
FastAPI routes, and PDF rendering -- runs for real.
"""

import io
import json
import shutil
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.services import pipeline as pipeline_module
from api.services.project_store import project_store


FAKE_PDF_BYTES = b"%PDF-1.4 fake screenplay content for tests"
PROJECTS_ROOT = Path(__file__).resolve().parent.parent / "outputs" / "projects"


def _screenplay_data(title: str = "Test Feature") -> dict:
    return {
        "title": title,
        "genre": "Drama",
        "logline": "A test logline.",
        "characters": [{"name": "ALEX", "description": "The lead."}],
        "locations": ["WAREHOUSE"],
        "props": ["PHONE"],
        "vehicles": [],
        "vfx_requirements": [],
        "scenes": [
            {
                "scene_number": 1,
                "heading": "INT. WAREHOUSE - DAY",
                "location": "WAREHOUSE",
                "time_of_day": "DAY",
                "characters": ["ALEX"],
                "summary": "Alex explores the warehouse.",
            }
        ],
        "scene_count": 1,
        "estimated_shoot_days": 1,
    }


def _budget_data() -> dict:
    return {
        "currency": "INR",
        "shoot_days": 1,
        "categories": [
            {"category": "Crew", "estimated_cost": 10000.0, "assumption": "Day rate."}
        ],
        "total_estimated_cost": 10000.0,
        "major_cost_drivers": ["Crew"],
        "budget_risks": ["Weather delay"],
    }


def _research_data() -> dict:
    return {
        "research_topic": "Warehouse filming access",
        "findings": [
            {
                "topic": "Access permit",
                "finding": "Example warehouse operators require advance notice.",
                "source_title": "Example Source",
                "source_url": "https://example.com/permits",
                "production_impact": "Book the permit two weeks ahead.",
                "confidence": "medium",
                "requires_local_verification": True,
            }
        ],
        "production_recommendations": [
            "Confirm access hours with the site owner."
        ],
    }


def _plan_data() -> dict:
    return {
        "title": "Test Feature Production Plan",
        "overall_strategy": "Single-location shoot over one day.",
        "location_strategy": ["Secure warehouse access in advance."],
        "equipment_strategy": ["Rent lighting kit."],
        "vfx_strategy": [],
        "resource_recommendations": [
            {
                "resource_type": "Location",
                "recommendation": "Use the researched warehouse.",
                "source_url": "https://example.com/permits",
                "evidence": "Example Source confirms access rules.",
                "estimated_cost": None,
            }
        ],
        "budget_adjustments": [],
        "production_risks": ["Permit delay"],
        "mitigation_strategies": ["Apply for the permit early."],
        "recommended_shoot_days": 1,
        "confidence": "medium",
    }


def _storyboard_data() -> dict:
    return {
        "title": "Test Feature Storyboard",
        "visual_style": "Naturalistic",
        "cinematography_strategy": "Handheld coverage.",
        "scenes": [
            {
                "scene_number": 1,
                "scene_heading": "INT. WAREHOUSE - DAY",
                "source_scene_summary": "Alex explores the warehouse.",
                "visual_goal": "Convey isolation.",
                "shots": [
                    {
                        "shot_number": 1,
                        "scene_number": 1,
                        "screenplay_evidence": "Alex explores the warehouse.",
                        "shot_type": "Wide",
                        "camera_angle": "Eye level",
                        "camera_movement": "Static",
                        "subject": "Alex",
                        "action": "Walks through the space.",
                        "visual_description": "Alex dwarfed by the empty warehouse.",
                        "lighting": "Natural window light",
                        "mood": "Tense",
                        "vfx_required": False,
                        "image_prompt": "Wide shot of a figure in an empty warehouse.",
                    }
                ],
            }
        ],
        "total_shots": 1,
    }


def _call_sheet_data() -> dict:
    return {
        "call_sheet_id": "CS-001",
        "project_title": "Test Feature",
        "production_company": "Test Productions",
        "project_manager": "TBD",
        "date": None,
        "genre": "Drama",
        "logline": "A test logline.",
        "shoot_days": [
            {
                "day_number": 1,
                "date": None,
                "location": "WAREHOUSE",
                "crew_call": "07:00",
                "first_shot": "08:00",
                "lunch_break": "13:00 - 14:00",
                "wrap": "18:00",
                "scenes_scheduled": [
                    {
                        "scene_number": 1,
                        "heading": "INT. WAREHOUSE - DAY",
                        "summary": "Alex explores the warehouse.",
                        "estimated_shooting_time": "2 hours",
                        "characters_present": ["ALEX"],
                        "props": ["PHONE"],
                        "vfx_requirements": [],
                        "notes": None,
                    }
                ],
                "cast_on_call": ["ALEX"],
                "crew_on_call": ["Director"],
                "required_props": ["PHONE"],
                "required_equipment": ["Lighting kit"],
                "production_notes": ["Confirm access with site owner."],
                "safety_and_logistics": [
                    "Confirm filming permit with warehouse operator."
                ],
            }
        ],
        "cast_list": [{"character_name": "ALEX", "actor_name": "TBD"}],
        "crew_list": [{"role": "Director", "name": "TBD"}],
    }


_STAGE_DATA = {
    "screenplay_analysis": _screenplay_data,
    "budget_analysis": _budget_data,
    "production_research": _research_data,
    "production_plan": _plan_data,
    "storyboard": _storyboard_data,
    "call_sheet": _call_sheet_data,
}


class _FakeEvent:
    """Duck-types the subset of google.adk.events.Event that pipeline.py
    actually reads: .author, .is_final_response(), .actions.state_delta.
    """

    def __init__(self, author, final, state_delta=None):
        self.author = author
        self._final = final
        self.actions = SimpleNamespace(state_delta=state_delta or {})
        self.content = None

    def is_final_response(self):
        return self._final


def _default_events():
    """The successful, full-pipeline event sequence."""
    return [
        _FakeEvent("script_agent", True, {"screenplay_analysis": _screenplay_data()}),
        _FakeEvent("budget_agent", True, {"budget_analysis": _budget_data()}),
        _FakeEvent(
            "production_research_agent", True, {"production_research": _research_data()}
        ),
        _FakeEvent("production_plan_agent", True, {"production_plan": _plan_data()}),
        _FakeEvent("storyboard_agent", True, {"storyboard": _storyboard_data()}),
        _FakeEvent("call_sheet_agent", True, {"call_sheet": _call_sheet_data()}),
    ]


def _fake_runner_class(events):
    """Build a stand-in for google.adk.runners.Runner whose run_async
    yields the given events, raising in place of yielding wherever an
    Exception instance appears in the list (simulating a mid-stream
    agent failure, exactly like a real ADK DynamicNodeFailError would).
    """

    class _FakeRunner:
        def __init__(self, *args, **kwargs):
            pass

        async def run_async(self, *args, **kwargs):
            for item in events:
                if isinstance(item, BaseException):
                    raise item
                yield item

    return _FakeRunner


@pytest.fixture(autouse=True)
def mock_agents(monkeypatch):
    """Replace the one seam that talks to Gemini/ADK for every test.

    Individual tests may re-patch `pipeline_module.Runner` again afterwards
    to simulate a specific failure sequence.
    """
    monkeypatch.setattr(pipeline_module, "Runner", _fake_runner_class(_default_events()))


@pytest.fixture(autouse=True)
def mock_storyboard_images(monkeypatch, tmp_path):
    """Replace the one seam that talks to Gemini image generation: write a
    tiny real PNG instead of calling Vertex AI.
    """
    from PIL import Image

    def _fake_generate(prompt, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (4, 4), color="black").save(output_path)
        return output_path

    monkeypatch.setattr(
        pipeline_module, "generate_scene_image_to_path", _fake_generate
    )


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def cleanup_projects():
    """Track project ids created by a test and remove their on-disk and
    in-memory state afterwards, so tests don't pollute outputs/projects/.
    """
    created: list[str] = []
    yield created
    for project_id in created:
        project_store._projects.pop(project_id, None)
        shutil.rmtree(PROJECTS_ROOT / project_id, ignore_errors=True)


def _create_project(client, cleanup_projects, filename="screenplay.pdf"):
    response = client.post(
        "/api/projects",
        files={
            "screenplay": (filename, io.BytesIO(FAKE_PDF_BYTES), "application/pdf")
        },
    )
    assert response.status_code == 201
    project = response.json()
    cleanup_projects.append(project["project_id"])
    return project


def _run_to_completion(client, project_id, timeout=10):
    run_response = client.post(f"/api/projects/{project_id}/run")
    assert run_response.status_code == 202

    deadline = time.time() + timeout
    while time.time() < deadline:
        status_response = client.get(f"/api/projects/{project_id}/status")
        assert status_response.status_code == 200
        project = status_response.json()
        if project["status"] in ("completed", "failed"):
            return project
        time.sleep(0.05)

    raise AssertionError("Pipeline did not finish within timeout")


class TestUploadValidation:
    def test_rejects_non_pdf(self, client, cleanup_projects):
        response = client.post(
            "/api/projects",
            files={
                "screenplay": (
                    "screenplay.txt",
                    io.BytesIO(b"not a pdf"),
                    "text/plain",
                )
            },
        )
        assert response.status_code == 400

    def test_rejects_empty_file(self, client, cleanup_projects):
        response = client.post(
            "/api/projects",
            files={
                "screenplay": (
                    "screenplay.pdf",
                    io.BytesIO(b""),
                    "application/pdf",
                )
            },
        )
        assert response.status_code == 400


class TestFullPipelineFlow:
    def test_pipeline_produces_every_artifact(self, client, cleanup_projects):
        project = _create_project(client, cleanup_projects)
        project_id = project["project_id"]

        final_project = _run_to_completion(client, project_id)
        assert final_project["status"] == "completed"
        assert final_project["title"] == "Test Feature"
        for stage in [
            "screenplay_analysis",
            "budget_analysis",
            "production_research",
            "production_plan",
            "storyboard",
            "call_sheet",
            "storyboard_images",
            "pdf",
        ]:
            assert final_project["stages"][stage]["status"] == "completed"

        screenplay = client.get(f"/api/projects/{project_id}/screenplay")
        assert screenplay.status_code == 200
        assert screenplay.json()["title"] == "Test Feature"

        budget = client.get(f"/api/projects/{project_id}/budget")
        assert budget.status_code == 200
        assert budget.json()["total_estimated_cost"] == 10000.0

        research = client.get(f"/api/projects/{project_id}/research")
        assert research.status_code == 200
        assert research.json()["findings"][0]["requires_local_verification"] is True

        plan = client.get(f"/api/projects/{project_id}/plan")
        assert plan.status_code == 200
        assert plan.json()["recommended_shoot_days"] == 1

        storyboard = client.get(f"/api/projects/{project_id}/storyboard")
        assert storyboard.status_code == 200
        assert storyboard.json()["total_shots"] == 1

        call_sheet = client.get(f"/api/projects/{project_id}/call-sheet")
        assert call_sheet.status_code == 200
        assert call_sheet.json()["shoot_days_total"] == 1

        pdf_response = client.get(f"/api/projects/{project_id}/call-sheet/pdf")
        assert pdf_response.status_code == 200
        assert pdf_response.headers["content-type"] == "application/pdf"
        assert len(pdf_response.content) > 0

        images = client.get(f"/api/projects/{project_id}/storyboard/images")
        assert images.status_code == 200
        image_list = images.json()
        assert len(image_list) == 1
        assert image_list[0]["scene_number"] == 1
        assert image_list[0]["shot_number"] == 1

        image_response = client.get(
            f"/api/projects/{project_id}/storyboard/images/1/1"
        )
        assert image_response.status_code == 200
        assert image_response.headers["content-type"] == "image/png"

        missing_image_response = client.get(
            f"/api/projects/{project_id}/storyboard/images/99/1"
        )
        assert missing_image_response.status_code == 404


class TestFailureHandling:
    def test_agent_failure_marks_the_right_stage_failed(
        self, client, cleanup_projects, monkeypatch
    ):
        events = [
            _FakeEvent(
                "script_agent", True, {"screenplay_analysis": _screenplay_data()}
            ),
            # Both sides of the concurrent budget/research pair start...
            _FakeEvent("budget_agent", False),
            _FakeEvent("production_research_agent", False),
            # ...but budget_agent never reaches a final event: ADK raises
            # instead, exactly like a real DynamicNodeFailError would.
            RuntimeError("Simulated Gemini failure in budget_agent"),
        ]
        monkeypatch.setattr(
            pipeline_module, "Runner", _fake_runner_class(events)
        )

        project = _create_project(client, cleanup_projects)
        project_id = project["project_id"]

        final_project = _run_to_completion(client, project_id)
        assert final_project["status"] == "failed"
        assert "Simulated Gemini failure" in final_project["error"]
        assert final_project["stages"]["screenplay_analysis"]["status"] == "completed"
        # The bug this guards against: budget and research run concurrently
        # under one ADK ParallelAgent, so a budget failure must not be
        # misattributed to production_research (or leave budget_analysis
        # stuck at "running" forever).
        assert final_project["stages"]["budget_analysis"]["status"] == "failed"
        assert final_project["stages"]["production_research"]["status"] == "failed"
        assert (
            "Simulated Gemini failure"
            in final_project["stages"]["budget_analysis"]["error"]
        )
        assert (
            "budget_analysis"
            in final_project["stages"]["production_research"]["error"]
        )

        # A failed pipeline must not silently expose a plan that was never
        # produced.
        plan = client.get(f"/api/projects/{project_id}/plan")
        assert plan.status_code == 404

    def test_invalid_agent_output_fails_the_project(
        self, client, cleanup_projects, monkeypatch
    ):
        # ADK's own output_schema validation already guards against
        # malformed JSON before it reaches state_delta; this test exercises
        # pipeline.py's *own* authoritative Pydantic re-validation by
        # supplying a dict missing a required field.
        invalid_screenplay = _screenplay_data()
        del invalid_screenplay["title"]

        events = [
            _FakeEvent(
                "script_agent", True, {"screenplay_analysis": invalid_screenplay}
            ),
        ]
        monkeypatch.setattr(pipeline_module, "Runner", _fake_runner_class(events))

        project = _create_project(client, cleanup_projects)
        project_id = project["project_id"]

        final_project = _run_to_completion(client, project_id)
        assert final_project["status"] == "failed"
        assert final_project["stages"]["screenplay_analysis"]["status"] == "failed"


class TestNotFound:
    def test_unknown_project_returns_404_everywhere(self, client):
        for path in [
            "",
            "/status",
            "/screenplay",
            "/budget",
            "/research",
            "/plan",
            "/storyboard",
            "/call-sheet",
            "/call-sheet/pdf",
        ]:
            response = client.get(f"/api/projects/does-not-exist{path}")
            assert response.status_code == 404

    def test_outputs_not_available_before_pipeline_runs(
        self, client, cleanup_projects
    ):
        project = _create_project(client, cleanup_projects)
        project_id = project["project_id"]
        for path in [
            "/screenplay",
            "/budget",
            "/research",
            "/plan",
            "/storyboard",
            "/call-sheet",
        ]:
            response = client.get(f"/api/projects/{project_id}{path}")
            assert response.status_code == 404


class TestProjectIsolation:
    def test_two_projects_do_not_share_outputs(
        self, client, cleanup_projects, monkeypatch
    ):
        def _events_with_title(title):
            return [
                _FakeEvent(
                    "script_agent", True, {"screenplay_analysis": _screenplay_data(title)}
                ),
                _FakeEvent("budget_agent", True, {"budget_analysis": _budget_data()}),
                _FakeEvent(
                    "production_research_agent",
                    True,
                    {"production_research": _research_data()},
                ),
                _FakeEvent(
                    "production_plan_agent", True, {"production_plan": _plan_data()}
                ),
                _FakeEvent(
                    "storyboard_agent", True, {"storyboard": _storyboard_data()}
                ),
                _FakeEvent(
                    "call_sheet_agent", True, {"call_sheet": _call_sheet_data()}
                ),
            ]

        monkeypatch.setattr(
            pipeline_module, "Runner", _fake_runner_class(_events_with_title("Project A"))
        )
        project_a = _create_project(client, cleanup_projects, "a.pdf")
        final_a = _run_to_completion(client, project_a["project_id"])

        monkeypatch.setattr(
            pipeline_module, "Runner", _fake_runner_class(_events_with_title("Project B"))
        )
        project_b = _create_project(client, cleanup_projects, "b.pdf")
        final_b = _run_to_completion(client, project_b["project_id"])

        assert final_a["project_id"] != final_b["project_id"]
        assert final_a["title"] == "Project A"
        assert final_b["title"] == "Project B"

        screenplay_a = client.get(
            f"/api/projects/{project_a['project_id']}/screenplay"
        ).json()
        screenplay_b = client.get(
            f"/api/projects/{project_b['project_id']}/screenplay"
        ).json()
        assert screenplay_a["title"] == "Project A"
        assert screenplay_b["title"] == "Project B"
