from pathlib import Path
from unittest.mock import patch

from packaging.version import Version
from typer.testing import CliRunner

from laken.cli import app

runner = CliRunner()


def test_deploy_uploads_built_wheel(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'laken'\nversion = '2.0.0'\n")
    built = tmp_path / "dist" / "laken-2.0.0-py3-none-any.whl"
    built.parent.mkdir()
    built.write_bytes(b"built")
    (tmp_path / "dist" / "laken-9.0.0-py3-none-any.whl").write_bytes(b"stale")
    monkeypatch.chdir(tmp_path)
    uploaded: list[Path] = []

    def capture_publish(*, config, wheel_path):
        uploaded.append(wheel_path)

    with (
        patch("laken.cli.build_wheel", return_value=(built, Version("2.0.0"))),
        patch("laken.cli.load_deploy_config"),
        patch("laken.cli.publish_wheel", side_effect=capture_publish),
    ):
        result = runner.invoke(app, ["deploy"])

    assert result.exit_code == 0
    assert uploaded == [built]
