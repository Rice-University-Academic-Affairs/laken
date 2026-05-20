from pathlib import Path


def repo_root() -> Path:
    path = Path(__file__).resolve().parent
    for candidate in [path, *path.parents]:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError("Could not find repo root (no pyproject.toml in parents)")
