from unittest.mock import MagicMock, patch

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import requests
from fake_fabric_fetcher import FakeFabricFetcher

from laken import LocalLakehouse
from laken.onelake_fetcher import OneLakeFabricFetcher, default_fabric_fetcher


def test_default_fabric_fetcher_without_credentials_returns_none(monkeypatch):
    monkeypatch.delenv("AZURE_TENANT_ID", raising=False)
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
    monkeypatch.delenv("AZURE_CLIENT_SECRET", raising=False)
    assert default_fabric_fetcher(workspace_name="WS", lakehouse="Sales_LH") is None


def test_default_fabric_fetcher_with_credentials_returns_fetcher(monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("FABRIC_WORKSPACE_NAME", "MyWorkspace")
    monkeypatch.setenv("FABRIC_LAKEHOUSE_NAME", "Sales_LH")
    monkeypatch.setenv("FABRIC_WORKSPACE_ID", "ws-id")

    fetcher = default_fabric_fetcher()

    assert isinstance(fetcher, OneLakeFabricFetcher)
    assert fetcher._workspace_name == "MyWorkspace"
    assert fetcher._lakehouse == "Sales_LH"
    assert fetcher._workspace_id == "ws-id"


def test_default_fabric_fetcher_credentials_without_workspace_returns_none(monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "secret")
    monkeypatch.delenv("FABRIC_WORKSPACE_NAME", raising=False)
    monkeypatch.delenv("FABRIC_LAKEHOUSE_NAME", raising=False)
    assert default_fabric_fetcher() is None


@patch("laken.onelake_fetcher._resolve_lakehouse_id", return_value="lh-resolved-id")
def test_default_fabric_fetcher_resolves_lakehouse_id(mock_resolve, monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("FABRIC_WORKSPACE_NAME", "MyWorkspace")
    monkeypatch.setenv("FABRIC_LAKEHOUSE_NAME", "Sales_LH")
    monkeypatch.setenv("FABRIC_WORKSPACE_ID", "ws-id")
    monkeypatch.delenv("FABRIC_LAKEHOUSE_ID", raising=False)

    fetcher = default_fabric_fetcher()

    mock_resolve.assert_called_once_with("ws-id", "Sales_LH")
    assert fetcher is not None
    assert fetcher._lakehouse_id == "lh-resolved-id"


@patch(
    "laken.onelake_fetcher._resolve_lakehouse_id",
    side_effect=requests.RequestException("api down"),
)
def test_default_fabric_fetcher_api_failure_leaves_lakehouse_id_none(mock_resolve, monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("FABRIC_WORKSPACE_NAME", "MyWorkspace")
    monkeypatch.setenv("FABRIC_LAKEHOUSE_NAME", "Sales_LH")
    monkeypatch.setenv("FABRIC_WORKSPACE_ID", "ws-id")
    monkeypatch.delenv("FABRIC_LAKEHOUSE_ID", raising=False)

    fetcher = default_fabric_fetcher()

    mock_resolve.assert_called_once()
    assert fetcher is not None
    assert fetcher._lakehouse_id is None


def test_default_fabric_fetcher_uses_env_lakehouse_id_without_api_call(monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("FABRIC_WORKSPACE_NAME", "MyWorkspace")
    monkeypatch.setenv("FABRIC_LAKEHOUSE_NAME", "Sales_LH")
    monkeypatch.setenv("FABRIC_WORKSPACE_ID", "ws-id")
    monkeypatch.setenv("FABRIC_LAKEHOUSE_ID", "lh-from-env")

    with patch("laken.onelake_fetcher._resolve_lakehouse_id") as mock_resolve:
        fetcher = default_fabric_fetcher()

    mock_resolve.assert_not_called()
    assert fetcher is not None
    assert fetcher._lakehouse_id == "lh-from-env"


def test_local_fetch_name_resolution_with_workspace_context(tmp_path):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher()
    fetcher.add(
        "MyWorkspace.Sales_LH.marketing.products",
        pa.table({"id": [1]}),
        version=1,
        size_bytes=100,
    )
    lakehouse = LocalLakehouse(
        root=root,
        fabric_fetcher=fetcher,
        workspace_name="MyWorkspace",
        lakehouse="Sales_LH",
    )

    result = lakehouse.read_table("marketing.products", frame_type="pandas")

    assert result["id"].tolist() == [1]


@patch("laken.onelake_fetcher.DeltaTable")
@patch("laken.onelake_fetcher.requests.post")
def test_onelake_fetcher_uses_oauth_and_fabric_delta(mock_post, mock_delta, monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant-id")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client-id")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "client-secret")
    mock_post.return_value.raise_for_status.return_value = None
    mock_post.return_value.json.return_value = {"access_token": "tok-123"}
    mock_dt = mock_delta.return_value
    mock_dt.version.return_value = 9
    mock_dt.get_add_actions.return_value = pa.table(
        {
            "path": ["part.parquet"],
            "size_bytes": [1234],
            "modification_time": [0],
            "num_records": [2],
        }
    )
    mock_dt.to_pyarrow_table.return_value = pa.table({"id": [1, 2]})
    mock_dataset = MagicMock()
    mock_dataset.head.return_value = pa.table({"id": [1]})
    mock_dt.to_pyarrow_dataset.return_value = mock_dataset

    fetcher = OneLakeFabricFetcher(workspace_name="MyWorkspace", lakehouse="Sales_LH")
    info = fetcher.inspect_table("marketing.products")
    table = fetcher.fetch_table("marketing.products", max_rows=1)

    token_call = mock_post.call_args
    assert token_call.args[0] == "https://login.microsoftonline.com/tenant-id/oauth2/v2.0/token"
    assert token_call.kwargs["data"]["grant_type"] == "client_credentials"
    assert token_call.kwargs["data"]["scope"] == "https://storage.azure.com/.default"
    assert mock_delta.call_args.kwargs["storage_options"]["bearer_token"] == "tok-123"
    assert mock_delta.call_args.kwargs["storage_options"]["use_fabric_endpoint"] == "true"
    assert (
        mock_delta.call_args.args[0] == "abfss://MyWorkspace@onelake.dfs.fabric.microsoft.com/"
        "Sales_LH.Lakehouse/Tables/marketing/products"
    )
    assert info.table == "MyWorkspace.Sales_LH.marketing.products"
    assert info.delta_version == 9
    assert info.size_bytes == 1234
    assert table.num_rows == 1
    mock_dt.to_pyarrow_dataset.assert_called_once()
    mock_dataset.head.assert_called_once_with(1)
    mock_dt.to_pyarrow_table.assert_not_called()


@patch("laken.onelake_fetcher.DeltaTable")
@patch("laken.onelake_fetcher.requests.post")
def test_onelake_fetcher_full_mirror_uses_to_pyarrow_table(mock_post, mock_delta, monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant-id")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client-id")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "client-secret")
    mock_post.return_value.raise_for_status.return_value = None
    mock_post.return_value.json.return_value = {"access_token": "tok"}
    mock_dt = mock_delta.return_value
    mock_dt.to_pyarrow_table.return_value = pa.table({"id": [1, 2, 3]})

    fetcher = OneLakeFabricFetcher(workspace_name="WS", lakehouse="LH")
    table = fetcher.fetch_table("products", max_rows=None)

    assert table.num_rows == 3
    mock_dt.to_pyarrow_table.assert_called_once()
    mock_dt.to_pyarrow_dataset.assert_not_called()


@patch("laken.onelake_fetcher.DeltaTable")
@patch("laken.onelake_fetcher.requests.post")
def test_onelake_fetcher_dbo_table_uri(mock_post, mock_delta, monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant-id")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client-id")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "client-secret")
    mock_post.return_value.raise_for_status.return_value = None
    mock_post.return_value.json.return_value = {"access_token": "tok"}
    mock_delta.return_value.version.return_value = 1
    mock_delta.return_value.metadata.return_value = None
    mock_delta.return_value.to_pyarrow_table.return_value = pa.table({"id": [1]})

    fetcher = OneLakeFabricFetcher(workspace_name="WS", lakehouse="LH")
    fetcher.inspect_table("products")

    uri = mock_delta.call_args.args[0]
    assert uri.endswith("LH.Lakehouse/Tables/products")


@patch("laken.onelake_fetcher.DeltaTable")
@patch("laken.onelake_fetcher.requests.post")
def test_onelake_fetcher_id_based_table_uri(mock_post, mock_delta, monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant-id")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client-id")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "client-secret")
    mock_post.return_value.raise_for_status.return_value = None
    mock_post.return_value.json.return_value = {"access_token": "tok"}
    mock_delta.return_value.version.return_value = 1
    mock_delta.return_value.metadata.return_value = None

    fetcher = OneLakeFabricFetcher(
        workspace_name="MyWorkspace",
        lakehouse="Sales_LH",
        workspace_id="ws-uuid",
        lakehouse_id="lh-uuid",
    )
    fetcher.inspect_table("marketing.products")

    assert mock_delta.call_args.args[0] == (
        "abfss://ws-uuid@onelake.dfs.fabric.microsoft.com/lh-uuid/Tables/marketing/products"
    )


@patch("laken.onelake_fetcher.DeltaTable")
@patch("laken.onelake_fetcher.requests.post")
def test_onelake_fetcher_cross_workspace_uses_name_based_uri(mock_post, mock_delta, monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant-id")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client-id")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "client-secret")
    mock_post.return_value.raise_for_status.return_value = None
    mock_post.return_value.json.return_value = {"access_token": "tok"}
    mock_delta.return_value.version.return_value = 1
    mock_delta.return_value.metadata.return_value = None

    fetcher = OneLakeFabricFetcher(
        workspace_name="MyWorkspace",
        lakehouse="Sales_LH",
        workspace_id="ws-uuid",
        lakehouse_id="lh-uuid",
    )
    fetcher.inspect_table("OtherWorkspace.Other_LH.dbo.products")

    assert mock_delta.call_args.args[0] == (
        "abfss://OtherWorkspace@onelake.dfs.fabric.microsoft.com/Other_LH.Lakehouse/Tables/products"
    )


@patch("laken.onelake_fetcher.DeltaStorageHandler")
@patch("laken.onelake_fetcher.requests.post")
def test_onelake_fetcher_fetch_csv(mock_post, mock_handler, monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant-id")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client-id")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "client-secret")
    mock_post.return_value.raise_for_status.return_value = None
    mock_post.return_value.json.return_value = {"access_token": "tok"}
    mock_instance = mock_handler.return_value
    mock_handle = mock_instance.open_input_file.return_value.__enter__.return_value
    mock_handle.read.return_value = b"id,name,value\n1,Alice,10.5\n"

    fetcher = OneLakeFabricFetcher(workspace_name="WS", lakehouse="LH")
    table = fetcher.fetch_file("examples/integration_test/example.csv")

    mock_instance.open_input_file.assert_called_once_with(
        "Files/examples/integration_test/example.csv"
    )
    assert table.column("id").to_pylist() == [1]


@patch("laken.onelake_fetcher.DeltaStorageHandler")
@patch("laken.onelake_fetcher.requests.post")
def test_onelake_fetcher_fetch_parquet(mock_post, mock_handler, monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant-id")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client-id")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "client-secret")
    mock_post.return_value.raise_for_status.return_value = None
    mock_post.return_value.json.return_value = {"access_token": "tok"}
    mock_instance = mock_handler.return_value
    mock_handle = mock_instance.open_input_file.return_value.__enter__.return_value
    sink = pa.BufferOutputStream()
    pq.write_table(pa.table({"id": [1, 2]}), sink)
    mock_handle.read.return_value = sink.getvalue().to_pybytes()

    fetcher = OneLakeFabricFetcher(workspace_name="WS", lakehouse="LH")
    table = fetcher.fetch_file("data/example.parquet")

    mock_instance.open_input_file.assert_called_once_with("Files/data/example.parquet")
    assert table.column("id").to_pylist() == [1, 2]


@patch("laken.onelake_fetcher.DeltaStorageHandler")
@patch("laken.onelake_fetcher.requests.post")
def test_onelake_fetcher_fetch_unsupported_extension(mock_post, mock_handler, monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant-id")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client-id")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "client-secret")
    mock_post.return_value.raise_for_status.return_value = None
    mock_post.return_value.json.return_value = {"access_token": "tok"}
    mock_instance = mock_handler.return_value
    mock_handle = mock_instance.open_input_file.return_value.__enter__.return_value
    mock_handle.read.return_value = b"not-a-table"

    fetcher = OneLakeFabricFetcher(workspace_name="WS", lakehouse="LH")

    with pytest.raises(ValueError, match="unsupported file type"):
        fetcher.fetch_file("data/example.json")
