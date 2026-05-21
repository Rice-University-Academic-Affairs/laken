from unittest.mock import patch

from typer.testing import CliRunner

from laken.cli import app

runner = CliRunner()


@patch("laken.cli.LocalLakehouse")
def test_status_command(mock_lh):
    mock_lh.return_value.status.return_value = [
        {
            "table": "products",
            "state": "mirror",
            "source_version": "3",
            "notes": "",
        }
    ]

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "products" in result.stdout
    mock_lh.return_value.status.assert_called_once()


@patch("laken.cli.LocalLakehouse")
def test_refresh_command(mock_lh):
    result = runner.invoke(app, ["refresh", "raw_faculty"])

    assert result.exit_code == 0
    mock_lh.return_value.refresh_table.assert_called_once_with("raw_faculty")


@patch("laken.cli.LocalLakehouse")
def test_reset_command(mock_lh):
    result = runner.invoke(app, ["reset", "raw_faculty"])

    assert result.exit_code == 0
    mock_lh.return_value.reset_table.assert_called_once_with("raw_faculty")


@patch("laken.cli.LocalLakehouse")
def test_refresh_command_surfaces_errors(mock_lh):
    mock_lh.return_value.refresh_table.side_effect = FileNotFoundError("table not found: x")

    result = runner.invoke(app, ["refresh", "x"])

    assert result.exit_code == 1
    assert "table not found" in result.stderr
