from pathlib import Path
from unittest.mock import MagicMock, patch

from packaging.version import Version
from typer.testing import CliRunner

from laken.cli import app

runner = CliRunner()


def test_deploy_uploads_wheel_from_build_not_dist_resolution(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    built = dist / "laken-2.0.0-py3-none-any.whl"
    built.write_bytes(b"built")
    (dist / "laken-9.0.0-py3-none-any.whl").write_bytes(b"stale")
    monkeypatch.chdir(tmp_path)
    metadata = MagicMock()
    metadata.name = "laken"
    uploaded: list[Path | None] = []

    def capture_upload(*_args, wheel_path=None, **_kwargs):
        uploaded.append(wheel_path)

    with (
        patch("laken.cli._build_project", return_value=(metadata, built, Version("2.0.0"))),
        patch("laken.cli._upload_project", side_effect=capture_upload),
        patch("laken.cli.load_deploy_config"),
        patch("laken.cli.publish_wheel"),
    ):
        result = runner.invoke(app, ["deploy"])

    assert result.exit_code == 0
    assert uploaded == [built]
