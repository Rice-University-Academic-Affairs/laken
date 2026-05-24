import re
import subprocess
from pathlib import Path

from packaging.utils import InvalidWheelFilename, parse_wheel_filename
from packaging.version import InvalidVersion, Version


def build_wheel(project_name: str) -> tuple[Path, Version]:
    root = Path.cwd()
    dist = root / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["uv", "build", "-q", "--no-build-logs", "--wheel", "-o", str(dist)],
        cwd=root,
        check=True,
    )
    return _find_wheel(dist, project_name)


def _find_wheel(dist: Path, project_name: str) -> tuple[Path, Version]:
    normalized = _normalize_name(project_name)
    matches: list[tuple[Version, Path]] = []
    for wheel in dist.glob("*.whl"):
        parsed = _parse_wheel(wheel)
        if parsed is None:
            continue
        name, version = parsed
        if _normalize_name(name) == normalized:
            matches.append((version, wheel))
    if not matches:
        raise FileNotFoundError(f"No wheel for {project_name!r} in {dist}")
    version, path = max(matches, key=lambda item: item[0])
    return path, version


def _parse_wheel(path: Path) -> tuple[str, Version] | None:
    try:
        name, version, _, _ = parse_wheel_filename(path.name)
    except InvalidWheelFilename:
        return None
    if isinstance(version, Version):
        return name, version
    try:
        return name, Version(version)
    except InvalidVersion:
        return None


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()
