import subprocess
from pathlib import Path


def run_build() -> None:
    subprocess.run(["uv", "build"], cwd=Path.cwd(), check=True)
