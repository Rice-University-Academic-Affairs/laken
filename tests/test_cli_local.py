from unittest.mock import MagicMock, patch

import pyarrow as pa
from fake_fabric_fetcher import FakeFabricFetcher
from typer.testing import CliRunner

from laken import LocalLakehouse
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


@patch("laken.local.default_fabric_fetcher")
def test_local_lakehouse_wires_default_fabric_fetcher(mock_default, tmp_path):
    fetcher = MagicMock()
    mock_default.return_value = fetcher

    lakehouse = LocalLakehouse(root=tmp_path / "workspace", lakehouse="Sales_LH")

    mock_default.assert_called_once_with(
        lakehouse="Sales_LH",
        workspace_id=None,
        workspace_name=None,
    )
    assert lakehouse._fabric_fetcher is fetcher


def test_local_lakehouse_explicit_fetcher_skips_default(tmp_path):
    fetcher = FakeFabricFetcher()
    fetcher.add("t", pa.table({"id": [1]}), version=1, size_bytes=10)

    with patch("laken.local.default_fabric_fetcher") as mock_default:
        lakehouse = LocalLakehouse(root=tmp_path / "workspace", fabric_fetcher=fetcher)

    mock_default.assert_not_called()
    assert lakehouse._fabric_fetcher is fetcher


def test_refresh_command_hydrates_with_default_fetcher(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fetcher = FakeFabricFetcher()
    fetcher.add("raw_faculty", pa.table({"id": [1]}), version=1, size_bytes=100)
    lakehouse = LocalLakehouse(fabric_fetcher=fetcher)
    lakehouse.read_table("raw_faculty", as_="pandas")
    fetcher.add("raw_faculty", pa.table({"id": [2]}), version=2, size_bytes=100)

    with patch("laken.local.default_fabric_fetcher", return_value=fetcher):
        result = runner.invoke(app, ["refresh", "raw_faculty"])

    assert result.exit_code == 0
    assert lakehouse.read_table("raw_faculty", as_="pandas")["id"].tolist() == [2]
