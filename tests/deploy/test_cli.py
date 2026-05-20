from typer.testing import CliRunner

from laken.cli import app

runner = CliRunner()


def test_help_exposes_commands():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "deploy" in result.output
    assert "status" in result.output
    assert "refresh" in result.output
    assert "reset" in result.output
    assert "build" not in result.output
    assert "upload" not in result.output


def test_build_and_upload_are_not_commands():
    for command in ["build", "upload"]:
        result = runner.invoke(app, [command])

        assert result.exit_code != 0
        assert "No such command" in result.output
