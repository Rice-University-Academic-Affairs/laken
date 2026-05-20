import json

import pandas as pd
import pyarrow as pa

from laken import LocalLakehouse
from laken.workspace import FabricTableInfo


class FakeFabricFetcher:
    def __init__(self):
        self.tables = {}
        self.limits = []

    def add(
        self,
        name: str,
        table: pa.Table,
        *,
        version: int,
        size_bytes: int,
        workspace_id: str = "abc",
        lakehouse_id: str = "def",
    ) -> None:
        self.tables[name] = {
            "table": table,
            "info": FabricTableInfo(
                table=name,
                delta_version=version,
                workspace_id=workspace_id,
                lakehouse_id=lakehouse_id,
                row_count=table.num_rows,
                size_bytes=size_bytes,
            ),
        }

    def inspect_table(self, name: str) -> FabricTableInfo:
        return self.tables[name]["info"]

    def fetch_table(self, name: str, *, limit: int | None = None) -> pa.Table:
        self.limits.append(limit)
        table = self.tables[name]["table"]
        if limit is None:
            return table
        return table.slice(0, limit)


def _metadata(root):
    with (root.parent / "metadata" / "tables.json").open(encoding="utf-8") as file:
        return json.load(file)["tables"]


def test_first_read_hydrates_full_delta_table_and_keeps_cache_stable(tmp_path, capsys):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher()
    fetcher.add(
        "raw_faculty",
        pa.table({"id": [1, 2], "name": ["Ada", "Grace"]}),
        version=42,
        size_bytes=100,
    )
    lakehouse = LocalLakehouse(root=root, fabric_fetcher=fetcher)

    result = lakehouse.read_table("raw_faculty", as_="pandas")

    assert result["id"].tolist() == [1, 2]
    assert (root / "Tables" / "raw_faculty" / "_delta_log").is_dir()
    assert _metadata(root)["raw_faculty"]["state"] == "mirror"
    assert _metadata(root)["raw_faculty"]["source"]["delta_version"] == 42
    assert "laken: fetching raw_faculty from Fabric..." in capsys.readouterr().out

    fetcher.add(
        "raw_faculty",
        pa.table({"id": [9], "name": ["Katherine"]}),
        version=45,
        size_bytes=100,
    )

    cached = lakehouse.read_table("raw_faculty", as_="pandas")

    assert cached["id"].tolist() == [1, 2]
    output = capsys.readouterr().out
    assert "laken: raw_faculty is cached from Fabric version 42." in output
    assert "laken: Fabric is now at version 45." in output


def test_large_table_hydrates_fixed_sample(tmp_path, capsys):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher()
    fetcher.add(
        "fact_events",
        pa.table({"id": [1, 2, 3, 4, 5]}),
        version=17,
        size_bytes=500,
    )
    lakehouse = LocalLakehouse(
        root=root,
        fabric_fetcher=fetcher,
        max_full_cache_bytes=100,
        sample_rows=3,
    )

    result = lakehouse.read_table("fact_events", as_="pandas")

    assert result["id"].tolist() == [1, 2, 3]
    assert fetcher.limits == [3]
    entry = _metadata(root)["fact_events"]
    assert entry["state"] == "sample"
    assert entry["cache"]["sample_rows"] == 3
    output = capsys.readouterr().out
    assert "laken: fact_events is too large to cache in full." in output
    assert "laken: cached a 3-row development sample instead." in output


def test_write_to_mirror_converts_to_local_and_reset_restores_fabric(tmp_path, capsys):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher()
    fetcher.add("raw_faculty", pa.table({"id": [1]}), version=1, size_bytes=100)
    lakehouse = LocalLakehouse(root=root, fabric_fetcher=fetcher)
    lakehouse.read_table("raw_faculty", as_="pandas")
    capsys.readouterr()

    lakehouse.write_table(pd.DataFrame({"id": [99]}), "raw_faculty")

    entry = _metadata(root)["raw_faculty"]
    assert entry["state"] == "local"
    assert entry["source"]["delta_version"] == 1
    assert "this write converts it to a local table" in capsys.readouterr().out

    fetcher.add("raw_faculty", pa.table({"id": [2]}), version=2, size_bytes=100)
    lakehouse.refresh_table("raw_faculty")

    assert lakehouse.read_table("raw_faculty", as_="pandas")["id"].tolist() == [99]
    assert "local-only and has no Fabric source to refresh" in capsys.readouterr().out

    lakehouse.reset_table("raw_faculty")

    assert lakehouse.read_table("raw_faculty", as_="pandas")["id"].tolist() == [2]
    assert _metadata(root)["raw_faculty"]["state"] == "mirror"
    assert _metadata(root)["raw_faculty"]["source"]["delta_version"] == 2


def test_status_marks_stale_and_sample_tables(tmp_path):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher()
    fetcher.add("raw_faculty", pa.table({"id": [1]}), version=1, size_bytes=100)
    fetcher.add("fact_events", pa.table({"id": [1, 2, 3]}), version=7, size_bytes=500)
    lakehouse = LocalLakehouse(
        root=root,
        fabric_fetcher=fetcher,
        max_full_cache_bytes=100,
        sample_rows=2,
    )
    lakehouse.read_table("raw_faculty", as_="pandas")
    lakehouse.read_table("fact_events", as_="pandas")
    fetcher.add("raw_faculty", pa.table({"id": [2]}), version=2, size_bytes=100)

    rows = {row["table"]: row for row in lakehouse.status()}

    assert rows["raw_faculty"]["notes"] == "stale: Fabric is 2"
    assert rows["fact_events"]["state"] == "sample"
    assert rows["fact_events"]["notes"] == "2-row sample"
