import pyarrow as pa
import pytest
from fake_fabric_fetcher import FakeFabricFetcher

from laken import Lakehouse, load_environment
from laken.local_lakehouse import LocalLakehouse
from laken.table_names import parse_table_ref


def test_public_exports():
    assert load_environment is not None
    assert Lakehouse is not None


def test_three_part_table_name_raises():
    with pytest.raises(ValueError, match="schema.table"):
        parse_table_ref("workspace.lakehouse.table")


def test_second_read_does_not_inspect_fabric(tmp_path):
    fetcher = FakeFabricFetcher()
    fetcher.add("t", pa.table({"id": [1]}), version=1, size_bytes=10)
    lakehouse = LocalLakehouse(root=tmp_path / "workspace", fabric_fetcher=fetcher)
    lakehouse.read_table("t", frame_type="pandas")
    fetcher.inspect_names.clear()
    lakehouse.read_table("t", frame_type="pandas")
    assert fetcher.inspect_names == []
