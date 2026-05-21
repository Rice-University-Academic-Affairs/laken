import json

import pandas as pd
import pyarrow as pa
import pytest
from fake_fabric_fetcher import FakeFabricFetcher

from laken import LocalLakehouse


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

    lakehouse.write_table(pd.DataFrame({"id": [99]}), "dbo.raw_faculty")

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


def test_refresh_mirror_updates_cached_data_and_metadata(tmp_path, capsys):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher()
    fetcher.add("raw_faculty", pa.table({"id": [1]}), version=1, size_bytes=100)
    lakehouse = LocalLakehouse(root=root, fabric_fetcher=fetcher)
    lakehouse.read_table("raw_faculty", as_="pandas")
    capsys.readouterr()

    fetcher.add("raw_faculty", pa.table({"id": [10, 11]}), version=3, size_bytes=100)
    lakehouse.refresh_table("raw_faculty")

    result = lakehouse.read_table("raw_faculty", as_="pandas")
    assert result["id"].tolist() == [10, 11]
    assert _metadata(root)["raw_faculty"]["state"] == "mirror"
    assert _metadata(root)["raw_faculty"]["source"]["delta_version"] == 3
    assert "laken: refreshed raw_faculty from Fabric version 3." in capsys.readouterr().out


def test_refresh_sample_table_re_fetches(tmp_path):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher()
    fetcher.add("fact_events", pa.table({"id": list(range(10))}), version=5, size_bytes=500)
    lakehouse = LocalLakehouse(
        root=root,
        fabric_fetcher=fetcher,
        max_full_cache_bytes=100,
        sample_rows=2,
    )
    lakehouse.read_table("fact_events", as_="pandas")
    fetcher.limits.clear()
    fetcher.add("fact_events", pa.table({"id": [100, 101, 102]}), version=6, size_bytes=500)

    lakehouse.refresh_table("fact_events")

    assert lakehouse.read_table("fact_events", as_="pandas")["id"].tolist() == [100, 101]
    assert fetcher.limits == [2]
    assert _metadata(root)["fact_events"]["source"]["delta_version"] == 6


def test_refresh_missing_table_raises(tmp_path):
    root = tmp_path / ".laken" / "workspace"
    lakehouse = LocalLakehouse(root=root, fabric_fetcher=FakeFabricFetcher())
    with pytest.raises(FileNotFoundError, match="table not found"):
        lakehouse.refresh_table("missing")


def test_reset_without_fabric_source_raises(tmp_path):
    root = tmp_path / ".laken" / "workspace"
    lakehouse = LocalLakehouse(root=root)
    lakehouse.write_table(pd.DataFrame({"id": [1]}), "dbo.local_only")
    with pytest.raises(ValueError, match="has no Fabric source to reset"):
        lakehouse.reset_table("local_only")


def test_read_warns_when_inspect_fails(tmp_path, capsys):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher()
    fetcher.add("raw_faculty", pa.table({"id": [1]}), version=1, size_bytes=100)
    lakehouse = LocalLakehouse(root=root, fabric_fetcher=fetcher)
    lakehouse.read_table("raw_faculty", as_="pandas")
    capsys.readouterr()
    fetcher.inspect_errors["raw_faculty"] = RuntimeError("network down")

    lakehouse.read_table("raw_faculty", as_="pandas")

    assert "laken: could not check Fabric freshness" in capsys.readouterr().out


def test_status_freshness_unknown_when_inspect_fails(tmp_path):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher()
    fetcher.add("raw_faculty", pa.table({"id": [1]}), version=1, size_bytes=100)
    lakehouse = LocalLakehouse(root=root, fabric_fetcher=fetcher)
    lakehouse.read_table("raw_faculty", as_="pandas")
    fetcher.inspect_errors["raw_faculty"] = RuntimeError("network down")

    rows = {row["table"]: row for row in lakehouse.status()}

    assert rows["raw_faculty"]["notes"] == "freshness unknown"


def test_cache_boundary_at_max_full_cache_bytes_uses_mirror(tmp_path):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher()
    fetcher.add("boundary", pa.table({"id": [1, 2]}), version=1, size_bytes=100)
    lakehouse = LocalLakehouse(
        root=root,
        fabric_fetcher=fetcher,
        max_full_cache_bytes=100,
    )
    lakehouse.read_table("boundary", as_="pandas")
    assert _metadata(root)["boundary"]["state"] == "mirror"
    assert fetcher.limits == [None]

    fetcher.limits.clear()
    fetcher.add("boundary2", pa.table({"id": [1]}), version=1, size_bytes=101)
    lakehouse.read_table("boundary2", as_="pandas")
    assert _metadata(root)["boundary2"]["state"] == "sample"
    assert fetcher.limits == [10000]


def test_hydrate_four_part_name_without_workspace_context(tmp_path):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher()
    fabric_name = "MyWorkspace.Sales_LH.dbo.products"
    fetcher.add(fabric_name, pa.table({"id": [7]}), version=2, size_bytes=50)
    lakehouse = LocalLakehouse(root=root, fabric_fetcher=fetcher)

    result = lakehouse.read_table(fabric_name, as_="pandas")

    assert result["id"].tolist() == [7]


def test_drop_table_removes_mirror_metadata(tmp_path):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher()
    fetcher.add("raw_faculty", pa.table({"id": [1]}), version=1, size_bytes=100)
    lakehouse = LocalLakehouse(root=root, fabric_fetcher=fetcher)
    lakehouse.read_table("raw_faculty", as_="pandas")
    assert "raw_faculty" in _metadata(root)

    lakehouse.drop_table("raw_faculty")

    assert "raw_faculty" not in _metadata(root)
    assert not lakehouse.table_exists("raw_faculty")


def test_read_without_fetcher_raises_file_not_found(tmp_path):
    lakehouse = LocalLakehouse(root=tmp_path / ".laken" / "workspace")
    with pytest.raises(FileNotFoundError, match="table not found"):
        lakehouse.read_table("missing", as_="pandas")


class TableNotFoundError(Exception):
    pass


def test_hydrate_maps_table_not_found_to_file_not_found(tmp_path):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher(inspect_errors={"missing": TableNotFoundError("gone")})
    lakehouse = LocalLakehouse(root=root, fabric_fetcher=fetcher)

    with pytest.raises(FileNotFoundError, match="table not found: missing"):
        lakehouse.read_table("missing", as_="pandas")


def test_refresh_uses_stored_four_part_source_table(tmp_path):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher()
    fabric_name = "MyWorkspace.Sales_LH.marketing.products"
    fetcher.add(fabric_name, pa.table({"id": [1]}), version=1, size_bytes=100)
    lakehouse = LocalLakehouse(
        root=root,
        fabric_fetcher=fetcher,
        workspace_name="MyWorkspace",
        lakehouse="Sales_LH",
    )

    lakehouse.read_table("marketing.products", as_="pandas")
    assert _metadata(root)["marketing.products"]["source"]["table"] == fabric_name
    fetcher.inspect_names.clear()
    fetcher.fetch_names.clear()
    fetcher.limits.clear()
    fetcher.add(fabric_name, pa.table({"id": [2]}), version=2, size_bytes=100)

    lakehouse.refresh_table("marketing.products")

    assert fetcher.inspect_names == [fabric_name]
    assert fetcher.fetch_names == [fabric_name]
    assert _metadata(root)["marketing.products"]["source"]["delta_version"] == 2
