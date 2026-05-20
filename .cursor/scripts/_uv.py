import os
import shlex
import subprocess
from pathlib import Path

from _repo import repo_root


def win_path_to_wsl(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive
    if drive:
        return f"/mnt/{drive[0].lower()}{resolved.as_posix()[len(drive):]}"
    return resolved.as_posix()


def run_uv(argv: list[str]) -> int:
    root = repo_root()
    command = shlex.join(["uv", *argv])
    if os.name == "nt":
        wsl_root = win_path_to_wsl(root)
        script = f"cd {shlex.quote(wsl_root)} && {command}"
        result = subprocess.run(["wsl", "-e", "bash", "-lc", script], check=False)
    else:
        result = subprocess.run(["uv", *argv], cwd=root, check=False)
    return result.returncode
