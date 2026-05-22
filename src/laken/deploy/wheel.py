import re
from pathlib import Path

from packaging.utils import InvalidWheelFilename, parse_wheel_filename
from packaging.version import InvalidVersion, Version


def wheel_from_build(project_name: str) -> tuple[Path, Version]:
    matches = _collect_matches(project_name)
    if not matches:
        raise FileNotFoundError(f"No wheel for project {project_name!r} found in dist/")
    if len(matches) == 1:
        version, path = matches[0]
        return path, version
    paths = [path for _, path in matches]
    names = ", ".join(path.name for path in paths)
    raise RuntimeError(
        f"Multiple wheels for {project_name!r} in dist/ after build: {names}. "
        "Run laken deploy again from a clean dist/."
    )


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

    return matches


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


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()
