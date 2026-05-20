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
        return []

    normalized_name = _normalize_name(project_name)
    matches: list[tuple[Version, Path]] = []
    for wheel in sorted(dist.glob("*.whl")):
        parsed = _parse_wheel(wheel)
        if parsed is None:
            continue
        distribution, version = parsed
        if _normalize_name(distribution) == normalized_name:
            matches.append((version, wheel))

    return matches


def resolve_wheel(project_name: str) -> tuple[Path, Version]:
    matches = _collect_matches(project_name)
    if not matches:
        raise FileNotFoundError(
            f"dist/ missing or no wheel for project {project_name!r}; run laken deploy"
        )
    if len(matches) > 1:
        names = ", ".join(path.name for _, path in matches)
        raise RuntimeError(f"Multiple wheels found for {project_name!r}: {names}")
    version, wheel = matches[0]
    return wheel, version
