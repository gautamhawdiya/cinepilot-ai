import json
from pathlib import Path
from threading import Lock

from api.schemas import ProjectState


class ProjectStore:
    """Small file-backed store for the local/hackathon API.

    This is intentionally not a database yet. It keeps project status
    available across normal API requests and avoids losing state merely
    because the process handles another request.
    """

    def __init__(self) -> None:
        self._projects: dict[str, ProjectState] = {}
        self._lock = Lock()
        self._root = Path(__file__).resolve().parents[2] / "outputs" / "projects"
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, project_id: str) -> Path:
        return self._root / project_id / "project_state.json"

    def create(self, project: ProjectState) -> ProjectState:
        with self._lock:
            self._projects[project.project_id] = project
            self._persist(project)
        return project

    def get(self, project_id: str) -> ProjectState | None:
        with self._lock:
            if project_id in self._projects:
                return self._projects[project_id]

            path = self._path(project_id)
            if not path.exists():
                return None

            project = ProjectState.model_validate_json(
                path.read_text(encoding="utf-8")
            )
            self._projects[project_id] = project
            return project

    def update(self, project: ProjectState) -> ProjectState:
        with self._lock:
            self._projects[project.project_id] = project
            self._persist(project)
        return project

    def _persist(self, project: ProjectState) -> None:
        path = self._path(project.project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(project.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )


project_store = ProjectStore()
