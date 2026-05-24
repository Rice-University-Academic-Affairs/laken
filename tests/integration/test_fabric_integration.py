import json

import pandas as pd
import pytest
from integration.conftest import INTEGRATION_TABLE, assert_frame_matches_spec, purge_local_table

from laken.frames import dataframe_kind, from_arrow

pytestmark = pytest.mark.integration


def _metadata_tables(root):
    with (root.parent / "metadata" / "tables.json").open(encoding="utf-8") as file:
        return json.load(file)["tables"]


class TestFabricFetcher:
    def test_inspect_integration_table(self, fabric_fetcher):
        info = fabric_fetcher.inspect_table(INTEGRATION_TABLE)
        assert info.delta_version >= 0
        assert INTEGRATION_TABLE in info.table
        assert info.size_bytes is not None
        assert info.size_bytes > 0

    def test_fetch_table_matches_spec(self, fabric_fetcher):
        table = fabric_fetcher.fetch_table(INTEGRATION_TABLE)
        assert_frame_matches_spec(from_arrow(table, "pandas"))

    def test_fetch_table_with_max_rows(self, fabric_fetcher):
        table = fabric_fetcher.fetch_table(INTEGRATION_TABLE, max_rows=3)
        assert table.num_rows == 3


class TestFabricLakehouseRead:
    def test_read_table_hydrates(self, fabric_lakehouse, df_kind):
        result = fabric_lakehouse.read_table(INTEGRATION_TABLE, frame_type=df_kind)
        assert dataframe_kind(result) == df_kind
        assert_frame_matches_spec(result)
        assert (fabric_lakehouse._table_dir(INTEGRATION_TABLE) / "_delta_log").is_dir()

    def test_read_table_second_read_uses_cache(self, fabric_lakehouse, capture_laken_logs):
        first = fabric_lakehouse.read_table(INTEGRATION_TABLE, frame_type="pandas")
        capture_laken_logs.clear()
        second = fabric_lakehouse.read_table(INTEGRATION_TABLE, frame_type="pandas")
        assert first.equals(second)
        assert "Fetching" not in capture_laken_logs.text

    def test_read_missing_raises(self, fabric_lakehouse):
        with pytest.raises(FileNotFoundError):
            fabric_lakehouse.read_table("missing_integration_table", frame_type="pandas")


class TestFabricLakehouseRefresh:
    def test_refresh_updates_mirror(self, fabric_lakehouse, capture_laken_logs):
        fabric_lakehouse.read_table(INTEGRATION_TABLE, frame_type="pandas")
        capture_laken_logs.clear()
        fabric_lakehouse._refresh_table(INTEGRATION_TABLE)
        result = fabric_lakehouse.read_table(INTEGRATION_TABLE, frame_type="pandas")
        assert_frame_matches_spec(result)
        assert "Refreshed" in capture_laken_logs.text
        entry = _metadata_tables(fabric_lakehouse._root)[INTEGRATION_TABLE]
        assert entry["state"] == "mirror"
        assert entry["cache"]["remote_size_bytes"] > 0


class TestFabricLakehouseWrite:
    def test_write_converts_mirror_to_local(
        self, fabric_lakehouse, clean_integration_table, local_row_pandas, capture_laken_logs
    ):
        fabric_lakehouse.read_table(INTEGRATION_TABLE, frame_type="pandas")
        start = len(capture_laken_logs.records)
        fabric_lakehouse.write_table(local_row_pandas, INTEGRATION_TABLE)
        entry = _metadata_tables(fabric_lakehouse._root)[INTEGRATION_TABLE]
        assert entry["state"] == "local"
        messages = [record.message for record in capture_laken_logs.records[start:]]
        assert any("converts it to a local table" in message for message in messages)

    def test_overwrite_replaces_rows(
        self, fabric_lakehouse, clean_integration_table, local_row_pandas
    ):
        fabric_lakehouse.read_table(INTEGRATION_TABLE, frame_type="pandas")
        fabric_lakehouse.write_table(local_row_pandas, INTEGRATION_TABLE, mode="overwrite")
        result = fabric_lakehouse.read_table(INTEGRATION_TABLE, frame_type="pandas")
        assert len(result) == 1

    def test_append_accumulates_rows(self, fabric_lakehouse, clean_integration_table):
        fabric_lakehouse.read_table(INTEGRATION_TABLE, frame_type="pandas")
        extra = pd.DataFrame({"id": [11], "name": ["Kate"], "value": [110.0]})
        fabric_lakehouse.write_table(extra, INTEGRATION_TABLE, mode="append")
        result = fabric_lakehouse.read_table(INTEGRATION_TABLE, frame_type="pandas")
        assert len(result) == 11

    def test_append_creates_table_when_missing(self, fabric_lakehouse, expected_pandas):
        scratch = "integration_append_scratch"
        fabric_lakehouse.write_table(expected_pandas.iloc[:2], scratch, mode="append")
        result = fabric_lakehouse.read_table(scratch, frame_type="pandas")
        assert len(result) == 2

    def test_reset_restores_fabric_mirror(
        self, fabric_lakehouse, clean_integration_table, local_row_pandas
    ):
        fabric_lakehouse.read_table(INTEGRATION_TABLE, frame_type="pandas")
        fabric_lakehouse.write_table(local_row_pandas, INTEGRATION_TABLE)
        fabric_lakehouse._reset_table(INTEGRATION_TABLE)
        result = fabric_lakehouse.read_table(INTEGRATION_TABLE, frame_type="pandas")
        assert_frame_matches_spec(result)
        entry = _metadata_tables(fabric_lakehouse._root)[INTEGRATION_TABLE]
        assert entry["state"] == "mirror"

    def test_refresh_local_only_is_noop(
        self, fabric_lakehouse, clean_integration_table, local_row_pandas, capture_laken_logs
    ):
        fabric_lakehouse.read_table(INTEGRATION_TABLE, frame_type="pandas")
        fabric_lakehouse.write_table(local_row_pandas, INTEGRATION_TABLE)
        start = len(capture_laken_logs.records)
        fabric_lakehouse._refresh_table(INTEGRATION_TABLE)
        messages = [record.message for record in capture_laken_logs.records[start:]]
        assert any("local-only" in message for message in messages)

    def test_purge_removes_local_cache(self, fabric_lakehouse, clean_integration_table):
        fabric_lakehouse.read_table(INTEGRATION_TABLE, frame_type="pandas")
        assert INTEGRATION_TABLE in _metadata_tables(fabric_lakehouse._root)
        purge_local_table(fabric_lakehouse, INTEGRATION_TABLE)
        assert not (fabric_lakehouse._table_dir(INTEGRATION_TABLE) / "_delta_log").is_dir()
        assert INTEGRATION_TABLE not in _metadata_tables(fabric_lakehouse._root)
