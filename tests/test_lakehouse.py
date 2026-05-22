import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pyarrow as pa
import pytest
from fake_fabric_fetcher import FakeFabricFetcher

import laken
from laken import FabricLakehouse, Lakehouse, LakehouseProtocol, LocalLakehouse
from laken.lakehouse import _is_fabric_context


def _fake_notebookutils():
    return SimpleNamespace(
        runtime=SimpleNamespace(
            context={
                "defaultLakehouseName": "Default_LH",
                "currentWorkspaceId": "ws-id-123",
                "currentWorkspaceName": "MyWorkspace",
            }
        )
    )


class TestLakehouseDispatch:
    def test_local_context_uses_local_lakehouse(self, tmp_path):
        lh = Lakehouse(root=tmp_path / "lakehouse")
        df = pd.DataFrame({"id": [1], "value": ["a"]})
        lh.write_table(df, "products")
        result = lh.read_table("products", as_="pandas")
        assert isinstance(lh._implementation, LocalLakehouse)
        assert result.equals(df)
        assert isinstance(lh, LakehouseProtocol)

    def test_local_lakehouse_receives_workspace_and_lakehouse(self, tmp_path):
        lh = Lakehouse(
            root=tmp_path / "lakehouse",
            lakehouse="Sales_LH",
            workspace_id="ws-123",
            workspace_name="MyWorkspace",
        )
        impl = lh._implementation
        assert isinstance(impl, LocalLakehouse)
        assert impl._lakehouse == "Sales_LH"
        assert impl._workspace_id == "ws-123"
        assert impl._workspace_name == "MyWorkspace"

    def test_fabric_context_uses_fabric_lakehouse(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "notebookutils", _fake_notebookutils())
        lh = Lakehouse(lakehouse="Sales_LH")
        assert isinstance(lh._implementation, FabricLakehouse)
        assert lh._implementation._lakehouse == "Sales_LH"
        assert lh._implementation._workspace_id == "ws-id-123"
        assert lh._implementation._workspace_name == "MyWorkspace"

    def test_fabric_detection_requires_runtime_context(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "notebookutils", SimpleNamespace())
        assert not _is_fabric_context()
        monkeypatch.setitem(sys.modules, "notebookutils", _fake_notebookutils())
        assert _is_fabric_context()

    def test_methods_delegate_to_selected_implementation(self):
        implementation = MagicMock()
        implementation.read_table.return_value = "result"
        with (
            patch("laken.lakehouse._is_fabric_context", return_value=True),
            patch("laken.fabric.FabricLakehouse", return_value=implementation),
        ):
            lh = Lakehouse(lakehouse="Sales_LH")
        assert lh.read_table("products", as_="pandas") == "result"
        implementation.read_table.assert_called_once_with(
            "products",
            as_="pandas",
            max_full_cache_bytes=None,
            max_sample_rows=None,
        )

    def test_module_functions_use_default_lakehouse(self):
        implementation = MagicMock()
        implementation.read_table.return_value = "result"
        with patch("laken.Lakehouse", return_value=implementation):
            assert laken.read_table("products", as_="pandas") == "result"
            laken.write_table("features", pd.DataFrame({"id": [1]}))
        implementation.read_table.assert_called_once_with(
            "products",
            as_="pandas",
            max_full_cache_bytes=None,
            max_sample_rows=None,
        )
        implementation.write_table.assert_called_once()
        assert implementation.write_table.call_args.args[1] == "features"


class TestLakehouseLocalOnlyMethods:
    def test_fabric_context_refresh_raises(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "notebookutils", _fake_notebookutils())
        lh = Lakehouse(lakehouse="Sales_LH")
        with pytest.raises(RuntimeError, match="only available in local mode"):
            lh.refresh_table("products")

    def test_fabric_context_reset_raises(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "notebookutils", _fake_notebookutils())
        lh = Lakehouse(lakehouse="Sales_LH")
        with pytest.raises(RuntimeError, match="only available in local mode"):
            lh.reset_table("products")

    def test_fabric_context_status_raises(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "notebookutils", _fake_notebookutils())
        lh = Lakehouse(lakehouse="Sales_LH")
        with pytest.raises(RuntimeError, match="only available in local mode"):
            lh.status()

    def test_lakehouse_hydrates_via_custom_fetcher(self, tmp_path):
        root = tmp_path / ".laken" / "workspace"
        fetcher = FakeFabricFetcher()
        fetcher.add("remote_table", pa.table({"id": [5]}), version=4, size_bytes=50)
        lh = Lakehouse(root=root, fabric_fetcher=fetcher)

        result = lh.read_table("remote_table", as_="pandas")

        assert result["id"].tolist() == [5]
        assert isinstance(lh._implementation, LocalLakehouse)

    @patch("laken.lakehouse.default_fabric_fetcher")
    def test_lakehouse_hydrates_via_default_fabric_fetcher(self, mock_default, tmp_path):
        root = tmp_path / ".laken" / "workspace"
        fetcher = FakeFabricFetcher()
        fetcher.add(
            "MyWorkspace.Sales_LH.dbo.remote_table",
            pa.table({"id": [9]}),
            version=1,
            size_bytes=50,
        )
        mock_default.return_value = fetcher

        lh = Lakehouse(
            root=root,
            lakehouse="Sales_LH",
            workspace_name="MyWorkspace",
        )

        result = lh.read_table("remote_table", as_="pandas")

        mock_default.assert_called_once_with(
            lakehouse="Sales_LH",
            workspace_id=None,
            workspace_name="MyWorkspace",
        )
        assert result["id"].tolist() == [9]
        assert lh._implementation._fabric_fetcher is fetcher
