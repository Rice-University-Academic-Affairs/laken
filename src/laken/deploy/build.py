import subprocess
from pathlib import Path

from packaging.version import Version

from laken.deploy.wheel import _clear_project_wheels, wheel_from_build


def run_build(project_name: str) -> tuple[Path, Version]:
    project_dir = Path.cwd()
    out_dir = project_dir / "dist"
    out_dir.mkdir(parents=True, exist_ok=True)
    _clear_project_wheels(out_dir, project_name)
    subprocess.run(
        [
            "uv",
            "build",
            "-q",
            "--no-build-logs",
            "--wheel",
            "-o",
            str(out_dir),
        ],
        cwd=project_dir,
        check=True,
    )
    return wheel_from_build(project_name, dist_dir=out_dir)
