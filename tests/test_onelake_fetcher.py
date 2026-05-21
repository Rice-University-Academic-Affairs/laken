import pyarrow as pa

from laken import LocalLakehouse
from laken.onelake_fetcher import default_fabric_fetcher
from laken.workspace import FabricTableInfo


class FakeFabricFetcher:
    def __init__(self):
        self.tables = {}

    def add(self, name: str, table: pa.Table, *, version: int, size_bytes: int) -> None:
        self.tables[name] = {
            "table": table,
            "info": FabricTableInfo(
                table=name,
                delta_version=version,
                size_bytes=size_bytes,
                row_count=table.num_rows,
            ),
        }

    def inspect_table(self, name: str) -> FabricTableInfo:
        return self.tables[name]["info"]

    def fetch_table(self, name: str, *, limit: int | None = None) -> pa.Table:
        table = self.tables[name]["table"]
        if limit is None:
            return table
        return table.slice(0, limit)


def test_default_fabric_fetcher_without_credentials_returns_none(monkeypatch):
    monkeypatch.delenv("AZURE_TENANT_ID", raising=False)
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
    monkeypatch.delenv("AZURE_CLIENT_SECRET", raising=False)
    assert default_fabric_fetcher(workspace_name="WS", lakehouse="Sales_LH") is None


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

    result = lakehouse.read_table("marketing.products", as_="pandas")

    assert result["id"].tolist() == [1]
