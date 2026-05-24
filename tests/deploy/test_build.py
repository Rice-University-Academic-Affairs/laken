import subprocess
from pathlib import Path

import pytest
from packaging.version import Version

from laken.deploy.build import build_wheel


def test_build_wheel_runs_uv_build_quietly(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'my-app'\nversion = '0.1.0'\n")
    captured: dict = {}

    def fake_run(cmd, *, cwd, check):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        out_dir = Path(cmd[cmd.index("-o") + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "my_app-0.1.0-py3-none-any.whl").write_bytes(b"")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(subprocess, "run", fake_run)

    wheel_path, version = build_wheel()

    assert captured["cmd"] == [
        "uv",
        "build",
        "-q",
        "--no-build-logs",
        "--wheel",
        "--clear",
        "-o",
        str(tmp_path / "dist"),
    ]
    assert captured["cwd"] == tmp_path
    assert wheel_path == tmp_path / "dist" / "my_app-0.1.0-py3-none-any.whl"
    assert version == Version("0.1.0")


def test_build_wheel_uses_project_dist_in_workspace(monkeypatch, tmp_path):
    member = tmp_path / "pkg"
    member.mkdir()
    (member / "pyproject.toml").write_text("[project]\nname = 'pkg'\nversion = '0.1.0'\n")
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'ws'\nversion = '0.0.0'\n[tool.uv.workspace]\nmembers = ['pkg']\n"
    )
    recorded: list[Path] = []

    def fake_run(cmd, *, cwd, check):
        out_dir = Path(cmd[cmd.index("-o") + 1])
        recorded.append(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "pkg-0.1.0-py3-none-any.whl").write_bytes(b"")

    monkeypatch.chdir(member)
    monkeypatch.setattr(subprocess, "run", fake_run)

    wheel_path, _ = build_wheel()

    assert recorded == [member / "dist"]
    assert wheel_path == member / "dist" / "pkg-0.1.0-py3-none-any.whl"
    assert not (tmp_path / "dist").exists()


def test_build_wheel_subprocess_failure_propagates(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'my-app'\nversion = '0.1.0'\n")

    def fake_run(*_args, **_kwargs):
        raise subprocess.CalledProcessError(1, ["uv", "build"])

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(subprocess.CalledProcessError):
        build_wheel()


def test_build_wheel_requires_exactly_one_wheel(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'my-app'\nversion = '0.1.0'\n")

    def fake_run(cmd, *, cwd, check):
        out_dir = Path(cmd[cmd.index("-o") + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "a-0.1.0-py3-none-any.whl").write_bytes(b"")
        (out_dir / "b-0.2.0-py3-none-any.whl").write_bytes(b"")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(FileNotFoundError, match="Expected one wheel"):
        build_wheel()
