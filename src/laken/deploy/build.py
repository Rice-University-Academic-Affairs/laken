import subprocess
from pathlib import Path

from laken.deploy.wheel import _collect_matches, _normalize_name, _parse_wheel


def run_build(project_name: str) -> None:
    dist = Path.cwd() / "dist"
    if dist.is_dir():
        normalized = _normalize_name(project_name)
        for wheel in dist.glob("*.whl"):
            parsed = _parse_wheel(wheel)
            if parsed is not None and _normalize_name(parsed[0]) == normalized:
                wheel.unlink()
    subprocess.run(["uv", "build"], cwd=Path.cwd(), check=True)
    if len(_collect_matches(project_name)) != 1:
        matches = _collect_matches(project_name)
        count = len(matches)
        raise RuntimeError(
            f"Expected one wheel for {project_name!r} in dist/ after build, found {count}"
        )
