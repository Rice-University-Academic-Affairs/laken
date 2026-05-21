import json

import pandas as pd
import pytest
from integration.conftest import (
    INTEGRATION_CSV,
    INTEGRATION_TABLE,
    assert_frame_matches_spec,
)

from laken.frames import from_arrow, kind_of

pytestmark = pytest.mark.integration


def _metadata_tables(root):
    with (root.parent / "metadata" / "tables.json").open(encoding="utf-8") as file:
        return json.load(file)["tables"]


class TestFabricFetcher:
    def test_inspect_integration_table(self, fabric_fetcher):
        info = fabric_fetcher.inspect_table(INTEGRATION_TABLE)
        assert info.delta_version >= 0
        assert INTEGRATION_TABLE in info.table

    def test_fetch_table_matches_spec(self, fabric_fetcher):
        table = fabric_fetcher.fetch_table(INTEGRATION_TABLE)
        assert_frame_matches_spec(from_arrow(table, "pandas"))

    def test_fetch_table_with_limit(self, fabric_fetcher):
        table = fabric_fetcher.fetch_table(INTEGRATION_TABLE, limit=3)
        assert table.num_rows == 3

    def test_fetch_csv_matches_spec(self, fabric_fetcher):
        table = fabric_fetcher.fetch_file(INTEGRATION_CSV)
        assert_frame_matches_spec(from_arrow(table, "pandas"))

    def test_fetch_table_four_part_name(self, fabric_fetcher):
        info = fabric_fetcher.inspect_table(INTEGRATION_TABLE)
        table = fabric_fetcher.fetch_table(info.table)
        assert table.num_rows == 10


class TestFabricLakehouseRead:
    def test_read_table_hydrates(self, fabric_lakehouse, df_kind):
        result = fabric_lakehouse.read_table(INTEGRATION_TABLE, as_=df_kind)
        assert kind_of(result) == df_kind
        assert_frame_matches_spec(result)
        assert (fabric_lakehouse._table_dir(INTEGRATION_TABLE) / "_delta_log").is_dir()

    def test_read_table_second_read_uses_cache(self, fabric_lakehouse, capsys):
        first = fabric_lakehouse.read_table(INTEGRATION_TABLE, as_="pandas")
        capsys.readouterr()
        second = fabric_lakehouse.read_table(INTEGRATION_TABLE, as_="pandas")
        assert first.equals(second)
        assert "fetching" not in capsys.readouterr().out

    def test_table_exists_after_hydrate(self, fabric_lakehouse):
        fabric_lakehouse.read_table(INTEGRATION_TABLE, as_="pandas")
        assert fabric_lakehouse.table_exists(INTEGRATION_TABLE)

    def test_list_tables_includes_hydrated_table(self, fabric_lakehouse):
        fabric_lakehouse.read_table(INTEGRATION_TABLE, as_="pandas")
        assert f"dbo.{INTEGRATION_TABLE}" in fabric_lakehouse.list_tables()

    def test_read_missing_raises(self, fabric_lakehouse):
        with pytest.raises(FileNotFoundError):
            fabric_lakehouse.read_table("missing_integration_table", as_="pandas")


class TestFabricLakehouseRefresh:
    def test_refresh_updates_mirror(self, fabric_lakehouse, capsys):
        fabric_lakehouse.read_table(INTEGRATION_TABLE, as_="pandas")
        capsys.readouterr()
        fabric_lakehouse.refresh_table(INTEGRATION_TABLE)
        result = fabric_lakehouse.read_table(INTEGRATION_TABLE, as_="pandas")
        assert_frame_matches_spec(result)
        assert "refreshed" in capsys.readouterr().out
        entry = _metadata_tables(fabric_lakehouse._root)[INTEGRATION_TABLE]
        assert entry["state"] == "mirror"

    def test_status_reports_mirror(self, fabric_lakehouse):
        fabric_lakehouse.read_table(INTEGRATION_TABLE, as_="pandas")
        rows = {row["table"]: row for row in fabric_lakehouse.status()}
        assert rows[INTEGRATION_TABLE]["state"] == "mirror"


class TestFabricLakehouseWrite:
    def test_write_converts_mirror_to_local(
        self, fabric_lakehouse, clean_integration_table, local_row_pandas, capsys
    ):
        fabric_lakehouse.read_table(INTEGRATION_TABLE, as_="pandas")
        capsys.readouterr()
        fabric_lakehouse.write_table(local_row_pandas, f"dbo.{INTEGRATION_TABLE}")
        entry = _metadata_tables(fabric_lakehouse._root)[INTEGRATION_TABLE]
        assert entry["state"] == "local"
        assert "converts it to a local table" in capsys.readouterr().out

    def test_overwrite_replaces_rows(
        self, fabric_lakehouse, clean_integration_table, local_row_pandas
    ):
        fabric_lakehouse.read_table(INTEGRATION_TABLE, as_="pandas")
        fabric_lakehouse.write_table(local_row_pandas, f"dbo.{INTEGRATION_TABLE}", mode="overwrite")
        result = fabric_lakehouse.read_table(INTEGRATION_TABLE, as_="pandas")
        assert len(result) == 1

    def test_append_accumulates_rows(self, fabric_lakehouse, clean_integration_table):
        fabric_lakehouse.read_table(INTEGRATION_TABLE, as_="pandas")
        extra = pd.DataFrame({"id": [11], "name": ["Kate"], "value": [110.0]})
        fabric_lakehouse.write_table(extra, f"dbo.{INTEGRATION_TABLE}", mode="append")
        result = fabric_lakehouse.read_table(INTEGRATION_TABLE, as_="pandas")
        assert len(result) == 11

    def test_append_creates_table_when_missing(self, fabric_lakehouse, expected_pandas):
        scratch = "dbo.integration_append_scratch"
        fabric_lakehouse.write_table(expected_pandas.iloc[:2], scratch, mode="append")
        result = fabric_lakehouse.read_table("integration_append_scratch", as_="pandas")
        assert len(result) == 2

    def test_reset_restores_fabric_mirror(
        self, fabric_lakehouse, clean_integration_table, local_row_pandas
    ):
        fabric_lakehouse.read_table(INTEGRATION_TABLE, as_="pandas")
        fabric_lakehouse.write_table(local_row_pandas, f"dbo.{INTEGRATION_TABLE}")
        fabric_lakehouse.reset_table(INTEGRATION_TABLE)
        result = fabric_lakehouse.read_table(INTEGRATION_TABLE, as_="pandas")
        assert_frame_matches_spec(result)
        entry = _metadata_tables(fabric_lakehouse._root)[INTEGRATION_TABLE]
        assert entry["state"] == "mirror"

    def test_refresh_local_only_is_noop(
        self, fabric_lakehouse, clean_integration_table, local_row_pandas, capsys
    ):
        fabric_lakehouse.read_table(INTEGRATION_TABLE, as_="pandas")
        fabric_lakehouse.write_table(local_row_pandas, f"dbo.{INTEGRATION_TABLE}")
        capsys.readouterr()
        fabric_lakehouse.refresh_table(INTEGRATION_TABLE)
        assert "local-only" in capsys.readouterr().out

    def test_drop_table_removes_local_cache(self, fabric_lakehouse, clean_integration_table):
        fabric_lakehouse.read_table(INTEGRATION_TABLE, as_="pandas")
        assert INTEGRATION_TABLE in _metadata_tables(fabric_lakehouse._root)
        fabric_lakehouse.drop_table(INTEGRATION_TABLE)
        assert not fabric_lakehouse.table_exists(INTEGRATION_TABLE)
        assert INTEGRATION_TABLE not in _metadata_tables(fabric_lakehouse._root)


class TestFabricLakehouseFiles:
    def test_fetch_csv_and_write_local_parquet(self, fabric_lakehouse, fabric_fetcher, df_kind):
        arrow = fabric_fetcher.fetch_file(INTEGRATION_CSV)
        frame = from_arrow(arrow, df_kind)
        fabric_lakehouse.write_file(frame, "integration/scratch.parquet")
        result = fabric_lakehouse.read_file("integration/scratch.parquet", as_=df_kind)
        assert kind_of(result) == df_kind
        assert_frame_matches_spec(result)

    def test_local_file_overwrite(self, fabric_lakehouse, fabric_fetcher):
        arrow = fabric_fetcher.fetch_file(INTEGRATION_CSV)
        frame = from_arrow(arrow, "pandas")
        fabric_lakehouse.write_file(frame, "integration/overwrite.parquet")
        replacement = pd.DataFrame({"id": [99], "name": ["Z"], "value": [0.0]})
        fabric_lakehouse.write_file(replacement, "integration/overwrite.parquet", mode="overwrite")
        result = fabric_lakehouse.read_file("integration/overwrite.parquet", as_="pandas")
        assert len(result) == 1

    def test_local_file_append(self, fabric_lakehouse, fabric_fetcher):
        arrow = fabric_fetcher.fetch_file(INTEGRATION_CSV)
        frame = from_arrow(arrow, "pandas")
        fabric_lakehouse.write_file(frame, "integration/append.parquet")
        extra = pd.DataFrame({"id": [11], "name": ["Kate"], "value": [110.0]})
        fabric_lakehouse.write_file(extra, "integration/append.parquet", mode="append")
        result = fabric_lakehouse.read_file("integration/append.parquet", as_="pandas")
        assert len(result) == 11

    def test_list_files_nested(self, fabric_lakehouse, fabric_fetcher):
        arrow = fabric_fetcher.fetch_file(INTEGRATION_CSV)
        fabric_lakehouse.write_file(from_arrow(arrow, "pandas"), "nested/integration.parquet")
        files = fabric_lakehouse.list_files("nested")
        assert "nested/integration.parquet" in files

    def test_file_exists_and_delete(self, fabric_lakehouse, fabric_fetcher):
        arrow = fabric_fetcher.fetch_file(INTEGRATION_CSV)
        path = "integration/delete.parquet"
        fabric_lakehouse.write_file(from_arrow(arrow, "pandas"), path)
        assert fabric_lakehouse.file_exists(path)
        fabric_lakehouse.delete_file(path)
        assert not fabric_lakehouse.file_exists(path)

    def test_read_missing_file_raises(self, fabric_lakehouse):
        with pytest.raises(FileNotFoundError):
            fabric_lakehouse.read_file("missing.parquet")
