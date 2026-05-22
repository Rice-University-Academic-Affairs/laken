import re
from pathlib import Path

from packaging.utils import InvalidWheelFilename, parse_wheel_filename
from packaging.version import InvalidVersion, Version


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _parse_wheel(wheel: Path) -> tuple[str, Version] | None:
    try:
        name, version, _, _ = parse_wheel_filename(wheel.name)
    except InvalidWheelFilename:
        return None
    if isinstance(version, Version):
        return name, version
    try:
        return name, Version(version)
    except InvalidVersion:
        return None


def _collect_matches(project_name: str) -> list[tuple[Version, Path]]:
    dist = Path.cwd() / "dist"
    if not dist.is_dir():
        raise FileNotFoundError("dist/ does not exist; run laken deploy from a project root")

    normalized_name = _normalize_name(project_name)
    matches: list[tuple[Version, Path]] = []
    for wheel in sorted(dist.glob("*.whl")):
        parsed = _parse_wheel(wheel)
        if parsed is None:
            continue
        distribution, version = parsed
        if _normalize_name(distribution) == normalized_name:
            matches.append((version, wheel))

    if not matches:
        raise FileNotFoundError(f"No wheel for project {project_name!r} found in dist/")
    return matches


def resolve_wheel(project_name: str, project_version: str | None = None) -> tuple[Path, Version]:
    matches = _collect_matches(project_name)
    target = Version(project_version) if project_version else max(v for v, _ in matches)
    wheels = [path for v, path in matches if v == target]
    if not wheels:
        found = ", ".join(str(v) for v, _ in matches)
        raise RuntimeError(
            f"No wheel for {project_name!r} version {project_version!r} in dist/ "
            f"(found: {found}); check the project version and run laken deploy"
        )
    if len(wheels) > 1:
        names = ", ".join(wheel.name for wheel in wheels)
        raise RuntimeError(f"Multiple wheels found for {project_name!r} {target}: {names}")
    return wheels[0], target
