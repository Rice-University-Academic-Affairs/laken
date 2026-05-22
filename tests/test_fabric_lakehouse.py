from unittest.mock import MagicMock, patch

import pyarrow as pa
import pytest

from laken import FabricLakehouse


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
        assert lh._explicit_lakehouse is False

    @patch("laken.fabric_lakehouse.FabricLakehouse._notebookutils")
    def test_explicit_lakehouse_flag(self, mock_nu_fn, mock_notebookutils):
        mock_nu_fn.return_value = mock_notebookutils
        lh = FabricLakehouse(lakehouse="Other_LH")
        assert lh._explicit_lakehouse is True
        assert lh._lakehouse == "Other_LH"


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
    @patch("laken.fabric_lakehouse._fabric_constants")
    @patch("laken.fabric_lakehouse.FabricLakehouse._notebookutils")
    def test_load_table_from_warehouse(
        self,
        mock_nu_fn,
        mock_constants_fn,
        mock_spark_fn,
        mock_spark,
        mock_notebookutils,
    ):
        constants = MagicMock()
        constants.WorkspaceId = "workspace-id-option"
        mock_constants_fn.return_value = constants
        mock_spark_fn.return_value = mock_spark
        mock_nu_fn.return_value = mock_notebookutils
        lh = FabricLakehouse()
        with patch("laken.fabric_lakehouse.from_spark", return_value="result") as from_spark:
            result = lh.load_table_from_warehouse(
                "orders",
                "SalesWarehouse",
                frame_type="pandas",
            )
        mock_spark.read.option.assert_called_once_with("workspace-id-option", "ws-id-123")
        mock_spark.read.synapsesql.assert_called_once_with("SalesWarehouse.dbo.orders")
        from_spark.assert_called_once_with(mock_spark.read.synapsesql.return_value, "pandas")
        assert result == "result"

    @patch("laken.fabric_lakehouse.get_or_create_spark_session")
    @patch("laken.fabric_lakehouse._fabric_constants")
    @patch("laken.fabric_lakehouse.FabricLakehouse._notebookutils")
    def test_load_table_from_warehouse_custom_workspace_without_schema(
        self,
        mock_nu_fn,
        mock_constants_fn,
        mock_spark_fn,
        mock_spark,
        mock_notebookutils,
    ):
        constants = MagicMock()
        constants.WorkspaceId = "workspace-id-option"
        mock_constants_fn.return_value = constants
        mock_spark_fn.return_value = mock_spark
        mock_nu_fn.return_value = mock_notebookutils
        lh = FabricLakehouse()
        with patch("laken.fabric_lakehouse.from_spark", return_value="result"):
            lh.load_table_from_warehouse(
                "orders",
                "SalesWarehouse",
                schema=None,
                workspace_id="custom-ws",
            )
        mock_spark.read.option.assert_called_once_with("workspace-id-option", "custom-ws")
        mock_spark.read.synapsesql.assert_called_once_with("SalesWarehouse.orders")

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
    def test_list_tables(self, mock_nu_fn, mock_notebookutils):
        mock_nu_fn.return_value = mock_notebookutils
        lh = FabricLakehouse()
        assert lh.list_tables() == ["dbo.products"]
        mock_notebookutils.lakehouse.listTables.assert_called_with(
            lakehouse="Default_LH",
            workspaceId="ws-id-123",
        )

    @patch("laken.fabric_lakehouse.get_or_create_spark_session")
    @patch("laken.fabric_lakehouse.FabricLakehouse._notebookutils")
    def test_table_exists(self, mock_nu_fn, mock_spark_fn, mock_spark, mock_notebookutils):
        mock_nu_fn.return_value = mock_notebookutils
        mock_spark_fn.return_value = mock_spark
        lh = FabricLakehouse()
        assert lh.table_exists("products")
        mock_spark.catalog.tableExists.assert_called_with("products")

    @patch("laken.fabric_lakehouse.get_or_create_spark_session")
    @patch("laken.fabric_lakehouse.FabricLakehouse._notebookutils")
    def test_drop_table(self, mock_nu_fn, mock_spark_fn, mock_spark, mock_notebookutils):
        mock_nu_fn.return_value = mock_notebookutils
        mock_spark_fn.return_value = mock_spark
        lh = FabricLakehouse()
        lh.drop_table("products")
        mock_spark.catalog.dropTable.assert_called_with("products", ignoreIfNotExists=True)

    @patch("laken.fabric_lakehouse.FabricLakehouse._notebookutils")
    def test_read_file_relative_path(self, mock_nu_fn, mock_notebookutils):
        mock_nu_fn.return_value = mock_notebookutils
        mock_handle = MagicMock()
        mock_handle.read.return_value = b"file-bytes"
        mock_notebookutils.fs.open.return_value.__enter__.return_value = mock_handle
        lh = FabricLakehouse()
        assert lh.read_file("data/sample.parquet") == b"file-bytes"
        mock_notebookutils.fs.open.assert_called_once_with(
            "Files/data/sample.parquet",
            "rb",
        )

    @patch("laken.fabric_lakehouse.to_arrow")
    @patch("laken.fabric_lakehouse.FabricLakehouse._notebookutils")
    def test_write_file_csv_writes_single_file(self, mock_nu_fn, mock_to_arrow, mock_notebookutils):
        mock_nu_fn.return_value = mock_notebookutils
        mock_to_arrow.return_value = pa.table({"id": [1], "value": ["a"]})
        mock_handle = MagicMock()
        mock_notebookutils.fs.open.return_value.__enter__.return_value = mock_handle
        lh = FabricLakehouse()
        lh.write_file(MagicMock(), "data/sample.csv")
        mock_notebookutils.fs.open.assert_called_once_with("Files/data/sample.csv", "wb")
        mock_handle.write.assert_called_once()
        assert b"id" in mock_handle.write.call_args.args[0]

    @patch("laken.fabric_lakehouse.FabricLakehouse._notebookutils")
    def test_read_file_csv_reads_spark_part_file(self, mock_nu_fn, mock_notebookutils):
        mock_nu_fn.return_value = mock_notebookutils
        mock_notebookutils.fs.exists.return_value = True
        entry = MagicMock()
        entry.name = "part-00000-abc.csv"
        mock_notebookutils.fs.ls.return_value = [entry]
        mock_handle = MagicMock()
        mock_handle.read.return_value = b"id,value\n1,a\n"
        mock_notebookutils.fs.open.return_value.__enter__.return_value = mock_handle
        lh = FabricLakehouse()
        assert lh.read_file("data/sample.csv") == b"id,value\n1,a\n"
        mock_notebookutils.fs.open.assert_called_once_with(
            "Files/data/sample.csv/part-00000-abc.csv",
            "rb",
        )

    @patch("laken.fabric_lakehouse.get_or_create_spark_session")
    @patch("laken.fabric_lakehouse.to_spark")
    @patch("laken.fabric_lakehouse.FabricLakehouse._notebookutils")
    def test_write_file_parquet(
        self, mock_nu_fn, mock_to_spark, mock_spark_fn, mock_spark, mock_notebookutils
    ):
        mock_nu_fn.return_value = mock_notebookutils
        mock_spark_fn.return_value = mock_spark
        spark_df = MagicMock()
        mock_to_spark.return_value = spark_df
        writer = MagicMock()
        spark_df.write = writer
        writer.mode.return_value = writer
        writer.format.return_value = writer
        lh = FabricLakehouse()
        lh.write_file(MagicMock(), "data/sample.parquet")
        writer.format.assert_called_with("parquet")
        writer.save.assert_called_with("Files/data/sample.parquet")

    @patch("laken.fabric_lakehouse.FabricLakehouse._notebookutils")
    def test_file_exists(self, mock_nu_fn, mock_notebookutils):
        mock_nu_fn.return_value = mock_notebookutils
        lh = FabricLakehouse()
        assert lh.file_exists("data/sample.parquet")
        mock_notebookutils.fs.exists.assert_called_with("Files/data/sample.parquet")

    @patch("laken.fabric_lakehouse.FabricLakehouse._notebookutils")
    def test_delete_file(self, mock_nu_fn, mock_notebookutils):
        mock_nu_fn.return_value = mock_notebookutils
        lh = FabricLakehouse()
        lh.delete_file("data/sample.parquet")
        mock_notebookutils.fs.rm.assert_called_with("Files/data/sample.parquet", recurse=False)


class TestFabricCrossLakehouse:
    @patch("laken.fabric_lakehouse.FabricLakehouse._notebookutils")
    def test_resolve_table_four_part(self, mock_nu_fn, mock_notebookutils):
        mock_nu_fn.return_value = mock_notebookutils
        lh = FabricLakehouse(
            lakehouse="Sales_LH",
            workspace_id="ws-id-123",
            workspace_name="MyWorkspace",
            lakehouse_id="lh-id-456",
        )
        assert lh._resolve_table_name("marketing.products") == (
            "MyWorkspace.Sales_LH.marketing.products"
        )

    @patch("laken.fabric_lakehouse.FabricLakehouse._notebookutils")
    def test_resolve_table_passes_through_existing_four_part_name(
        self, mock_nu_fn, mock_notebookutils
    ):
        mock_nu_fn.return_value = mock_notebookutils
        lh = FabricLakehouse(
            lakehouse="Sales_LH",
            workspace_id="ws-id-123",
            workspace_name="MyWorkspace",
            lakehouse_id="lh-id-456",
        )
        name = "MyWorkspace.Sales_LH.marketing.products"
        assert lh._resolve_table_name(name) == name

    @patch("laken.fabric_lakehouse.FabricLakehouse._notebookutils")
    def test_file_path_abfss(self, mock_nu_fn, mock_notebookutils):
        mock_nu_fn.return_value = mock_notebookutils
        lh = FabricLakehouse(
            lakehouse="Sales_LH",
            workspace_id="ws-id-123",
            workspace_name="MyWorkspace",
            lakehouse_id="lh-id-456",
        )
        assert lh._file_path("data/sample.parquet") == (
            "abfss://ws-id-123@onelake.dfs.fabric.microsoft.com/lh-id-456/Files/data/sample.parquet"
        )

    @patch("laken.fabric_lakehouse.FabricLakehouse._notebookutils")
    def test_cross_lakehouse_requires_workspace_and_lakehouse_ids(
        self, mock_nu_fn, mock_notebookutils
    ):
        mock_nu_fn.return_value = mock_notebookutils
        lh = FabricLakehouse(
            lakehouse="Sales_LH",
            workspace_id="ws-id-123",
            workspace_name="MyWorkspace",
            lakehouse_id=None,
        )
        lh._lakehouse_id = None
        with pytest.raises(ValueError, match="lakehouse_id"):
            lh._resolve_table_name("products")
