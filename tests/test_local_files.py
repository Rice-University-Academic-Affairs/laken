import pandas as pd
import pytest

from laken.frames import dataframe_kind


class TestLocalFiles:
    def test_write_then_read(self, lakehouse, sample_df, df_kind):
        lakehouse.write_file(sample_df, "data/sample.parquet")
        result = lakehouse.read_file("data/sample.parquet", frame_type=df_kind)
        assert dataframe_kind(result) == df_kind

    def test_overwrite_replaces(self, lakehouse, sample_pandas):
        lakehouse.write_file(sample_pandas, "data/sample.parquet")
        replacement = pd.DataFrame({"id": [99], "value": ["z"]})
        lakehouse.write_file(replacement, "data/sample.parquet", mode="overwrite")
        result = lakehouse.read_file("data/sample.parquet", frame_type="pandas")
        assert len(result) == 1
        assert result.iloc[0]["id"] == 99

    def test_append_adds_rows(self, lakehouse, sample_pandas):
        lakehouse.write_file(sample_pandas, "data/sample.parquet")
        extra = pd.DataFrame({"id": [3], "value": ["c"]})
        lakehouse.write_file(extra, "data/sample.parquet", mode="append")
        result = lakehouse.read_file("data/sample.parquet", frame_type="pandas")
        assert len(result) == 3

    def test_list_files_nested(self, lakehouse, sample_pandas):
        lakehouse.write_file(sample_pandas, "nested/sample.parquet")
        files = lakehouse.list_files("nested")
        assert "nested/sample.parquet" in files

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
