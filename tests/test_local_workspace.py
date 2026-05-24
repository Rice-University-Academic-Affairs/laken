import json
import shutil

import pandas as pd
import pyarrow as pa
import pytest
from fake_fabric_fetcher import FakeFabricFetcher

from laken.local_lakehouse import LocalLakehouse


def _metadata(root):
    with (root.parent / "metadata" / "tables.json").open(encoding="utf-8") as file:
        return json.load(file)["tables"]


def test_first_read_hydrates_full_delta_table_and_keeps_cache_stable(tmp_path, capture_laken_logs):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher()
    fetcher.add(
        "raw_faculty",
        pa.table({"id": [1, 2], "name": ["Ada", "Grace"]}),
        version=42,
        size_bytes=100,
    )
    lakehouse = LocalLakehouse(root=root, fabric_fetcher=fetcher)

    result = lakehouse.read_table("raw_faculty", frame_type="pandas")

    assert result["id"].tolist() == [1, 2]
    assert (root / "Tables" / "raw_faculty" / "_delta_log").is_dir()
    assert _metadata(root)["raw_faculty"]["state"] == "mirror"
    assert _metadata(root)["raw_faculty"]["source"]["delta_version"] == 42
    assert "Fetching raw_faculty from Fabric" in capture_laken_logs.text

    fetcher.add(
        "raw_faculty",
        pa.table({"id": [9], "name": ["Katherine"]}),
        version=45,
        size_bytes=100,
    )

    cached = lakehouse.read_table("raw_faculty", frame_type="pandas")

    assert cached["id"].tolist() == [1, 2]
    assert fetcher.inspect_names == ["raw_faculty"]


def test_large_table_hydrates_fixed_sample(tmp_path, capture_laken_logs):
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
        max_mirror_mb=0,
        max_sample_rows=3,
    )

    result = lakehouse.read_table("fact_events", frame_type="pandas")

    assert result["id"].tolist() == [1, 2, 3]
    assert fetcher.max_rows == [3]
    entry = _metadata(root)["fact_events"]
    assert entry["state"] == "sample"
    assert entry["cache"]["max_sample_rows"] == 3
    assert "over 0 MB limit" in capture_laken_logs.text
    assert "Caching a 3-row development sample instead." in capture_laken_logs.text


def test_write_to_mirror_converts_to_local_and_reset_restores_fabric(tmp_path, capture_laken_logs):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher()
    fetcher.add("raw_faculty", pa.table({"id": [1]}), version=1, size_bytes=100)
    lakehouse = LocalLakehouse(root=root, fabric_fetcher=fetcher)
    lakehouse.read_table("raw_faculty", frame_type="pandas")
    capture_laken_logs.clear()

    lakehouse.write_table(pd.DataFrame({"id": [99]}), "raw_faculty")

    entry = _metadata(root)["raw_faculty"]
    assert entry["state"] == "local"
    assert entry["source"]["delta_version"] == 1
    assert "converts it to a local table" in capture_laken_logs.text

    fetcher.add("raw_faculty", pa.table({"id": [2]}), version=2, size_bytes=100)
    lakehouse._refresh_table("raw_faculty")

    assert lakehouse.read_table("raw_faculty", frame_type="pandas")["id"].tolist() == [99]
    assert "local-only and has no Fabric source to refresh" in capture_laken_logs.text

    lakehouse._reset_table("raw_faculty")

    assert lakehouse.read_table("raw_faculty", frame_type="pandas")["id"].tolist() == [2]
    assert _metadata(root)["raw_faculty"]["state"] == "mirror"
    assert _metadata(root)["raw_faculty"]["source"]["delta_version"] == 2


def test_refresh_mirror_updates_cached_data_and_metadata(tmp_path, capture_laken_logs):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher()
    fetcher.add("raw_faculty", pa.table({"id": [1]}), version=1, size_bytes=100)
    lakehouse = LocalLakehouse(root=root, fabric_fetcher=fetcher)
    lakehouse.read_table("raw_faculty", frame_type="pandas")
    capture_laken_logs.clear()

    fetcher.add("raw_faculty", pa.table({"id": [10, 11]}), version=3, size_bytes=100)
    lakehouse._refresh_table("raw_faculty")

    result = lakehouse.read_table("raw_faculty", frame_type="pandas")
    assert result["id"].tolist() == [10, 11]
    assert _metadata(root)["raw_faculty"]["state"] == "mirror"
    assert _metadata(root)["raw_faculty"]["source"]["delta_version"] == 3
    assert "Refreshed raw_faculty from Fabric version 3." in capture_laken_logs.text


def test_refresh_sample_table_keeps_sample_when_mirror_limit_increased(tmp_path):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher()
    fetcher.add("fact_events", pa.table({"id": list(range(10))}), version=5, size_bytes=500)
    lakehouse = LocalLakehouse(
        root=root,
        fabric_fetcher=fetcher,
        max_mirror_mb=0,
        max_sample_rows=2,
    )
    lakehouse.read_table("fact_events", frame_type="pandas")
    fetcher.max_rows.clear()
    fetcher.add("fact_events", pa.table({"id": [100, 101, 102, 103]}), version=6, size_bytes=50)

    lakehouse = LocalLakehouse(
        root=root,
        fabric_fetcher=fetcher,
        max_mirror_mb=100,
        max_sample_rows=10000,
    )
    lakehouse._refresh_table("fact_events")

    assert lakehouse.read_table("fact_events", frame_type="pandas")["id"].tolist() == [100, 101]
    assert fetcher.max_rows == [2]
    assert _metadata(root)["fact_events"]["state"] == "sample"


def test_refresh_sample_table_re_fetches(tmp_path):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher()
    fetcher.add("fact_events", pa.table({"id": list(range(10))}), version=5, size_bytes=500)
    lakehouse = LocalLakehouse(
        root=root,
        fabric_fetcher=fetcher,
        max_mirror_mb=0,
        max_sample_rows=2,
    )
    lakehouse.read_table("fact_events", frame_type="pandas")
    fetcher.max_rows.clear()
    fetcher.add("fact_events", pa.table({"id": [100, 101, 102]}), version=6, size_bytes=500)

    lakehouse._refresh_table("fact_events")

    assert lakehouse.read_table("fact_events", frame_type="pandas")["id"].tolist() == [100, 101]
    assert fetcher.max_rows == [2]
    assert _metadata(root)["fact_events"]["source"]["delta_version"] == 6


def test_refresh_missing_table_raises(tmp_path):
    root = tmp_path / ".laken" / "workspace"
    lakehouse = LocalLakehouse(root=root, fabric_fetcher=FakeFabricFetcher())
    with pytest.raises(FileNotFoundError, match="table not found"):
        lakehouse._refresh_table("missing")


def test_reset_without_fabric_source_raises(tmp_path):
    root = tmp_path / ".laken" / "workspace"
    lakehouse = LocalLakehouse(root=root)
    lakehouse.write_table(pd.DataFrame({"id": [1]}), "local_only")
    with pytest.raises(ValueError, match="has no Fabric source to reset"):
        lakehouse._reset_table("local_only")


def test_cache_boundary_at_max_mirror_mb_uses_mirror(tmp_path):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher()
    fetcher.add("boundary", pa.table({"id": [1, 2]}), version=1, size_bytes=1_000_000)
    lakehouse = LocalLakehouse(
        root=root,
        fabric_fetcher=fetcher,
        max_mirror_mb=1,
    )
    lakehouse.read_table("boundary", frame_type="pandas")
    assert _metadata(root)["boundary"]["state"] == "mirror"
    assert fetcher.max_rows == [None]

    fetcher.max_rows.clear()
    fetcher.add("boundary2", pa.table({"id": [1]}), version=1, size_bytes=1_000_001)
    lakehouse.read_table("boundary2", frame_type="pandas")
    assert _metadata(root)["boundary2"]["state"] == "sample"
    assert fetcher.max_rows == [10000]


def test_read_table_override_cache_thresholds(tmp_path):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher()
    fetcher.add("wide", pa.table({"id": [1]}), version=1, size_bytes=200)
    lakehouse = LocalLakehouse(
        root=root,
        fabric_fetcher=fetcher,
        max_mirror_mb=0,
    )
    lakehouse.read_table("wide", frame_type="pandas", max_mirror_mb=1)
    assert _metadata(root)["wide"]["state"] == "mirror"
    assert fetcher.max_rows == [None]


def test_read_three_part_name_raises(tmp_path):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher()
    lakehouse = LocalLakehouse(root=root, fabric_fetcher=fetcher)

    with pytest.raises(ValueError, match="schema.table"):
        lakehouse.read_table("MyWorkspace.Sales_LH.products", frame_type="pandas")


def test_read_rehydrates_when_delta_exists_without_metadata(tmp_path):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher()
    fetcher.add("raw_faculty", pa.table({"id": [1]}), version=1, size_bytes=100)
    lakehouse = LocalLakehouse(root=root, fabric_fetcher=fetcher)
    lakehouse.read_table("raw_faculty", frame_type="pandas")
    fetcher.add("raw_faculty", pa.table({"id": [2]}), version=2, size_bytes=100)
    lakehouse._metadata.remove("raw_faculty")

    result = lakehouse.read_table("raw_faculty", frame_type="pandas")

    assert result["id"].tolist() == [2]


def test_read_uses_orphan_local_delta_when_metadata_missing(tmp_path):
    root = tmp_path / ".laken" / "workspace"
    lakehouse = LocalLakehouse(root=root)
    lakehouse.write_table(pd.DataFrame({"id": [1]}), "local_only")
    lakehouse._metadata.remove("local_only")

    result = lakehouse.read_table("local_only", frame_type="pandas")

    assert result["id"].tolist() == [1]


def test_purge_removes_mirror_metadata(tmp_path):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher()
    fetcher.add("raw_faculty", pa.table({"id": [1]}), version=1, size_bytes=100)
    lakehouse = LocalLakehouse(root=root, fabric_fetcher=fetcher)
    lakehouse.read_table("raw_faculty", frame_type="pandas")
    assert "raw_faculty" in _metadata(root)

    shutil.rmtree(lakehouse._table_dir("raw_faculty"), ignore_errors=True)
    lakehouse._metadata.remove("raw_faculty")

    assert "raw_faculty" not in _metadata(root)
    assert not (lakehouse._table_dir("raw_faculty") / "_delta_log").is_dir()


def test_read_without_fetcher_raises_file_not_found(tmp_path):
    lakehouse = LocalLakehouse(root=tmp_path / ".laken" / "workspace")
    with pytest.raises(FileNotFoundError, match="table not found"):
        lakehouse.read_table("missing", frame_type="pandas")


def test_write_delta_table_restores_backup_on_failure(tmp_path, monkeypatch):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher()
    fetcher.add("raw_faculty", pa.table({"id": [1]}), version=1, size_bytes=100)
    lakehouse = LocalLakehouse(root=root, fabric_fetcher=fetcher)
    lakehouse.read_table("raw_faculty", frame_type="pandas")
    table_dir = root / "Tables" / "raw_faculty"
    assert (table_dir / "_delta_log").is_dir()

    def fail_write(*args, **kwargs):
        raise RuntimeError("write failed")

    monkeypatch.setattr("laken.local_lakehouse.write_deltalake", fail_write)
    fetcher.add("raw_faculty", pa.table({"id": [9]}), version=2, size_bytes=100)

    with pytest.raises(RuntimeError, match="write failed"):
        lakehouse._refresh_table("raw_faculty")

    assert lakehouse.read_table("raw_faculty", frame_type="pandas")["id"].tolist() == [1]
    assert (table_dir / "_delta_log").is_dir()


def test_hydrate_maps_table_not_found_to_file_not_found(tmp_path):
    from deltalake.exceptions import TableNotFoundError

    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher(inspect_errors={"missing": TableNotFoundError("gone")})
    lakehouse = LocalLakehouse(root=root, fabric_fetcher=fetcher)

    with pytest.raises(FileNotFoundError, match="table not found: missing"):
        lakehouse.read_table("missing", frame_type="pandas")


def test_refresh_uses_stored_fabric_source_table(tmp_path):
    root = tmp_path / ".laken" / "workspace"
    fetcher = FakeFabricFetcher()
    fabric_name = "MyWorkspace.Sales_LH.marketing.products"
    fetcher.add(fabric_name, pa.table({"id": [1]}), version=1, size_bytes=100)
    lakehouse = LocalLakehouse(
        root=root,
        fabric_fetcher=fetcher,
        workspace_name="MyWorkspace",
        workspace_id="ws-id",
        lakehouse="Sales_LH",
        lakehouse_id="lh-id",
    )

    lakehouse.read_table("marketing.products", frame_type="pandas")
    assert _metadata(root)["marketing.products"]["source"]["table"] == fabric_name
    fetcher.inspect_names.clear()
    fetcher.fetch_names.clear()
    fetcher.max_rows.clear()
    fetcher.add(fabric_name, pa.table({"id": [2]}), version=2, size_bytes=100)

    lakehouse._refresh_table("marketing.products")

    assert fetcher.inspect_names == [fabric_name]
    assert fetcher.fetch_names == [fabric_name]
    assert _metadata(root)["marketing.products"]["source"]["delta_version"] == 2
