import subprocess
from pathlib import Path

from packaging.utils import parse_wheel_filename
from packaging.version import InvalidVersion, Version


def build_wheel() -> tuple[Path, Version]:
    root = Path.cwd()
    dist = root / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "uv",
            "build",
            "-q",
            "--no-build-logs",
            "--wheel",
            "--clear",
            "-o",
            str(dist),
        ],
        cwd=root,
        check=True,
    )
    wheels = list(dist.glob("*.whl"))
    if len(wheels) != 1:
        count = len(wheels)
        raise FileNotFoundError(f"Expected one wheel in {dist}, found {count}")
    path = wheels[0]
    _, version, _, _ = parse_wheel_filename(path.name)
    if isinstance(version, Version):
        return path, version
    try:
        return path, Version(str(version))
    except InvalidVersion as exc:
        raise RuntimeError(f"Invalid version in wheel name {path.name}") from exc
