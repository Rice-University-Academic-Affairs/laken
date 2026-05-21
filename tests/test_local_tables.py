import pandas as pd
import pytest

from laken.frames import kind_of


class TestLocalTables:
    def test_write_read_dbo(self, lakehouse, sample_df, df_kind):
        lakehouse.write_table(sample_df, "products")
        result = lakehouse.read_table("products", as_=df_kind)
        assert kind_of(result) == df_kind
        assert (lakehouse._table_dir("products") / "_delta_log").is_dir()

    def test_write_read_schema(self, lakehouse, sample_df, df_kind):
        lakehouse.write_table(sample_df, "marketing.products")
        result = lakehouse.read_table("marketing.products", as_=df_kind)
        assert kind_of(result) == df_kind

    def test_load_table_from_warehouse_reads_file(self, lakehouse, sample_df, df_kind):
        lakehouse.write_file(sample_df, "warehouse/products.parquet")
        result = lakehouse.load_table_from_warehouse(
            "warehouse/products.parquet",
            "SalesWarehouse",
            as_=df_kind,
        )
        assert kind_of(result) == df_kind

    def test_overwrite_resets(self, lakehouse, sample_pandas):
        lakehouse.write_table(sample_pandas, "products")
        replacement = pd.DataFrame({"id": [99], "value": ["z"]})
        lakehouse.write_table(replacement, "products", mode="overwrite")
        result = lakehouse.read_table("products", as_="pandas")
        assert len(result) == 1

    def test_append_accumulates(self, lakehouse, sample_pandas):
        lakehouse.write_table(sample_pandas, "products")
        extra = pd.DataFrame({"id": [3], "value": ["c"]})
        lakehouse.write_table(extra, "products", mode="append")
        result = lakehouse.read_table("products", as_="pandas")
        assert len(result) == 3

    def test_append_creates_missing_table(self, lakehouse, sample_pandas):
        lakehouse.write_table(sample_pandas, "products", mode="append")
        result = lakehouse.read_table("products", as_="pandas")
        assert len(result) == 2

    def test_list_tables_sorted(self, lakehouse, sample_pandas):
        lakehouse.write_table(sample_pandas, "products")
        lakehouse.write_table(sample_pandas, "marketing.products")
        assert lakehouse.list_tables() == ["dbo.products", "marketing.products"]

    def test_table_exists_true(self, lakehouse, sample_pandas):
        lakehouse.write_table(sample_pandas, "products")
        assert lakehouse.table_exists("products")

    def test_table_exists_false(self, lakehouse):
        assert not lakehouse.table_exists("products")

    def test_drop_table_removes(self, lakehouse, sample_pandas):
        lakehouse.write_table(sample_pandas, "products")
        lakehouse.drop_table("products")
        assert not lakehouse.table_exists("products")

    def test_read_missing_raises(self, lakehouse):
        with pytest.raises(FileNotFoundError):
            lakehouse.read_table("products")
