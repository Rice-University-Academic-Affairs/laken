import shutil
import subprocess
from pathlib import Path


def clean_dist() -> None:
    dist = Path.cwd() / "dist"
    if dist.exists():
        shutil.rmtree(dist)


def run_build() -> None:
    clean_dist()
    subprocess.run(["uv", "build"], cwd=Path.cwd(), check=True)
