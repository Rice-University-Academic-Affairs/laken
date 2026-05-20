from pathlib import Path
import re


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def resolve_wheel(project_name: str) -> Path:
    dist = Path.cwd() / "dist"
    if not dist.is_dir():
        raise FileNotFoundError("dist/ does not exist; run laken build first")

    normalized_name = _normalize_name(project_name)
    matches: list[tuple[str, Path]] = []
    for wheel in sorted(dist.glob("*.whl")):
        parts = wheel.name[:-4].split("-")
        if len(parts) < 5:
            continue
        distribution, version = parts[0], parts[1]
        if _normalize_name(distribution) == normalized_name:
            matches.append((version, wheel))

    if not matches:
        raise FileNotFoundError(f"No wheel for project {project_name!r} found in dist/")

    highest_version = sorted({version for version, _ in matches})[-1]
    highest_matches = [wheel for version, wheel in matches if version == highest_version]
    if len(highest_matches) > 1:
        names = ", ".join(wheel.name for wheel in highest_matches)
        raise RuntimeError(f"Multiple wheels found for {project_name!r} {highest_version}: {names}")
    return highest_matches[0]
