from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fake_fabric_fetcher import FakeFabricFetcher

from laken import LocalLakehouse
from laken.frames import dataframe_kind, from_arrow


class TestLocalFiles:
    def test_write_then_read(self, lakehouse, sample_df, df_kind):
        lakehouse.write_file(sample_df, "data/sample.parquet")
        data = lakehouse.read_file("data/sample.parquet")
        result = from_arrow(pq.read_table(pa.BufferReader(data)), df_kind)
        assert dataframe_kind(result) == df_kind

    def test_overwrite_replaces(self, lakehouse, sample_pandas):
        import pandas as pd

        lakehouse.write_file(sample_pandas, "data/sample.parquet")
        replacement = pd.DataFrame({"id": [99], "value": ["z"]})
        lakehouse.write_file(replacement, "data/sample.parquet", mode="overwrite")
        data = lakehouse.read_file("data/sample.parquet")
        result = from_arrow(pq.read_table(pa.BufferReader(data)), "pandas")
        assert len(result) == 1
        assert result.iloc[0]["id"] == 99

    def test_append_writes_part_file_without_reading_existing(self, lakehouse, sample_pandas):
        import pandas as pd

        lakehouse.write_file(sample_pandas, "data/sample.parquet")
        with patch.object(pq, "read_table") as read_table:
            extra = pd.DataFrame({"id": [3], "value": ["c"]})
            lakehouse.write_file(extra, "data/sample.parquet", mode="append")
        read_table.assert_not_called()
        dataset = lakehouse._file_path("data/sample.parquet").parent / "sample.parquet.d"
        assert dataset.is_dir()
        assert len(list(dataset.glob("part-*.parquet"))) == 2

    def test_append_adds_rows(self, lakehouse, sample_pandas):
        import pandas as pd

        lakehouse.write_file(sample_pandas, "data/sample.parquet")
        extra = pd.DataFrame({"id": [3], "value": ["c"]})
        lakehouse.write_file(extra, "data/sample.parquet", mode="append")
        data = lakehouse.read_file("data/sample.parquet")
        result = from_arrow(pq.read_table(pa.BufferReader(data)), "pandas")
        assert len(result) == 3

    def test_file_exists_true(self, lakehouse, sample_pandas):
        lakehouse.write_file(sample_pandas, "data/sample.parquet")
        assert lakehouse.file_exists("data/sample.parquet")

    def test_file_exists_false(self, lakehouse):
        assert not lakehouse.file_exists("missing.parquet")

    def test_delete_file_removes(self, lakehouse, sample_pandas):
        lakehouse.write_file(sample_pandas, "data/sample.parquet")
        lakehouse.delete_file("data/sample.parquet")
        assert not lakehouse.file_exists("data/sample.parquet")

    def test_read_missing_raises(self, lakehouse):
        with pytest.raises(FileNotFoundError):
            lakehouse.read_file("missing.parquet")

    def test_invalid_path_raises(self, lakehouse, sample_pandas):
        with pytest.raises(ValueError):
            lakehouse.write_file(sample_pandas, "../escape.parquet")

    def test_read_hydrates_from_fabric_fetcher(self, tmp_path):
        root = tmp_path / "workspace"
        fetcher = FakeFabricFetcher()
        fetcher.add_file("remote/data.bin", b"payload")
        lakehouse = LocalLakehouse(
            root=root,
            fabric_fetcher=fetcher,
            workspace_name="WS",
            workspace_id="ws-id",
            lakehouse="LH",
            lakehouse_id="lh-id",
        )
        assert lakehouse.read_file("remote/data.bin") == b"payload"
        assert (root / "Files" / "remote" / "data.bin").read_bytes() == b"payload"
