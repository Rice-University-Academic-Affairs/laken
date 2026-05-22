import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectMetadata:
    name: str
    version: str

    def wheel_version_pin(self) -> str | None:
        return self.version or None


def read_project_metadata(pyproject_path: Path | None = None) -> ProjectMetadata:
    path = pyproject_path or Path.cwd() / "pyproject.toml"
    data = tomllib.loads(path.read_text())
    project = data.get("project", {})
    name = project.get("name")
    if not name:
        raise ValueError("[project].name is required in pyproject.toml")
    pin = _wheel_version_pin(project)
    return ProjectMetadata(name=str(name), version=pin or "")


def _wheel_version_pin(project: dict) -> str | None:
    version = project.get("version")
    if version:
        return str(version)
    return None
