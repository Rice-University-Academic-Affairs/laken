from unittest.mock import MagicMock, patch

import pytest

from laken.fabric_lakehouse import FabricLakehouse


def _mock_runtime_context():
    return {
        "defaultLakehouseName": "Default_LH",
        "currentWorkspaceId": "ws-id-123",
        "currentWorkspaceName": "MyWorkspace",
    }


@pytest.fixture
def mock_spark():
    spark = MagicMock()
    reader = MagicMock()
    spark.read = reader
    reader.table.return_value = MagicMock()
    reader.parquet.return_value = MagicMock()
    reader.option.return_value = reader
    reader.synapsesql.return_value = MagicMock()
    spark.catalog.tableExists.return_value = True
    return spark


@pytest.fixture
def mock_notebookutils():
    nu = MagicMock()
    nu.runtime.context = _mock_runtime_context()
    entry = MagicMock()
    entry.schema = "dbo"
    entry.name = "products"
    nu.lakehouse.listTables.return_value = [entry]
    file_entry = MagicMock()
    file_entry.name = "sample.parquet"
    nu.fs.ls.return_value = [file_entry]
    nu.fs.exists.return_value = True
    return nu


class TestFabricRuntimeContext:
    @patch("laken.fabric_lakehouse.FabricLakehouse._notebookutils")
    def test_missing_workspace_name_does_not_raise(self, mock_nu_fn):
        nu = MagicMock()
        nu.runtime.context = {
            "defaultLakehouseName": "Default_LH",
            "currentWorkspaceId": "ws-id-123",
        }
        mock_nu_fn.return_value = nu
        lh = FabricLakehouse()
        assert lh._workspace_name is None
        assert lh._workspace_id == "ws-id-123"

    @patch("laken.fabric_lakehouse.FabricLakehouse._notebookutils")
    def test_defaults_from_context(self, mock_nu_fn, mock_notebookutils):
        mock_nu_fn.return_value = mock_notebookutils
        lh = FabricLakehouse()
        assert lh._lakehouse == "Default_LH"
        assert lh._workspace_id == "ws-id-123"
        assert lh._workspace_name == "MyWorkspace"


class TestFabricDefaultLakehouse:
    @patch("laken.fabric_lakehouse.FabricLakehouse._notebookutils")
    def test_resolve_bare_table_name_passes_through(self, mock_nu_fn, mock_notebookutils):
        mock_nu_fn.return_value = mock_notebookutils
        lh = FabricLakehouse()
        assert lh._resolve_table_name("products") == "products"

    @patch("laken.fabric_lakehouse.get_or_create_spark_session")
    @patch("laken.fabric_lakehouse.FabricLakehouse._notebookutils")
    def test_read_table_uses_schema_table(
        self, mock_nu_fn, mock_spark_fn, mock_spark, mock_notebookutils
    ):
        mock_spark_fn.return_value = mock_spark
        mock_nu_fn.return_value = mock_notebookutils
        lh = FabricLakehouse()
        with patch("laken.fabric_lakehouse.from_spark", return_value="result") as from_spark:
            result = lh.read_table("marketing.products", frame_type="pandas")
        mock_spark.read.table.assert_called_once_with("marketing.products")
        from_spark.assert_called_once()
        assert result == "result"

    @patch("laken.fabric_lakehouse.get_or_create_spark_session")
    @patch("laken.fabric_lakehouse.to_spark")
    def test_write_table_delta(self, mock_to_spark, mock_spark_fn, mock_spark):
        mock_spark_fn.return_value = mock_spark
        spark_df = MagicMock()
        mock_to_spark.return_value = spark_df
        writer = MagicMock()
        spark_df.write = writer
        writer.mode.return_value = writer
        writer.format.return_value = writer
        with patch("laken.fabric_lakehouse.FabricLakehouse._notebookutils") as mock_nu_fn:
            nu = MagicMock()
            nu.runtime.context = _mock_runtime_context()
            mock_nu_fn.return_value = nu
            lh = FabricLakehouse()
        lh.write_table(MagicMock(), "products", mode="append")
        writer.mode.assert_called_with("append")
        writer.format.assert_called_with("delta")
        writer.saveAsTable.assert_called_with("products")

    @patch("laken.fabric_lakehouse.FabricLakehouse._notebookutils")
    def test_resolve_three_part_name_raises(self, mock_nu_fn, mock_notebookutils):
        mock_nu_fn.return_value = mock_notebookutils
        lh = FabricLakehouse()
        with pytest.raises(ValueError, match="schema.table"):
            lh._resolve_table_name("MyWorkspace.Sales_LH.products")
