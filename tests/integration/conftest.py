import os
import shutil

import pandas as pd
import polars as pl
import pytest

from laken.local_lakehouse import LocalLakehouse
from laken.onelake_fetcher import (
    OneLakeFabricFetcher,
    _azure_credentials_available,
    default_fabric_fetcher,
)

INTEGRATION_TABLE = "example_integration_test"

EXPECTED_ROWS = [
    {"id": 1, "name": "Alice", "value": 10.5},
    {"id": 2, "name": "Bob", "value": 20.0},
    {"id": 3, "name": "Charlie", "value": 30.5},
    {"id": 4, "name": "Diana", "value": 40.0},
    {"id": 5, "name": "Evan", "value": 50.5},
    {"id": 6, "name": "Fiona", "value": 60.0},
    {"id": 7, "name": "George", "value": 70.5},
    {"id": 8, "name": "Hannah", "value": 80.0},
    {"id": 9, "name": "Ian", "value": 90.5},
    {"id": 10, "name": "Julia", "value": 100.0},
]


def _require_integration_fixtures(fetcher: OneLakeFabricFetcher) -> None:
    expected = len(EXPECTED_ROWS)
    table = fetcher.fetch_table(INTEGRATION_TABLE)
    assert table.num_rows == expected, (
        f"Integration table {INTEGRATION_TABLE!r} must exist in Fabric with "
        f"{expected} rows (got {table.num_rows})"
    )


def fabric_credentials_configured() -> bool:
    if not _azure_credentials_available():
        return False
    return bool(
        os.getenv("FABRIC_WORKSPACE_NAME")
        and os.getenv("FABRIC_LAKEHOUSE_NAME")
        and os.getenv("FABRIC_WORKSPACE_ID")
        and os.getenv("FABRIC_LAKEHOUSE_ID")
    )


def assert_frame_matches_spec(frame) -> None:
    if isinstance(frame, pl.DataFrame):
        assert frame.height == len(EXPECTED_ROWS)
        assert frame.columns == ["id", "name", "value"]
        for index, expected in enumerate(EXPECTED_ROWS):
            row = frame.row(index, named=True)
            assert row["id"] == expected["id"]
            assert row["name"] == expected["name"]
            assert row["value"] == expected["value"]
        return
    assert len(frame) == len(EXPECTED_ROWS)
    assert list(frame.columns) == ["id", "name", "value"]
    for index, expected in enumerate(EXPECTED_ROWS):
        row = frame.iloc[index]
        assert row["id"] == expected["id"]
        assert row["name"] == expected["name"]
        assert row["value"] == expected["value"]


@pytest.fixture(scope="session")
def fabric_configured():
    if not fabric_credentials_configured():
        pytest.skip("Fabric integration credentials are not configured")


@pytest.fixture(scope="session")
def fabric_fetcher(fabric_configured) -> OneLakeFabricFetcher:
    fetcher = default_fabric_fetcher()
    assert fetcher is not None
    _require_integration_fixtures(fetcher)
    return fetcher


@pytest.fixture
def fabric_lakehouse(tmp_path, fabric_fetcher) -> LocalLakehouse:
    return LocalLakehouse(
        root=tmp_path / "workspace",
        fabric_fetcher=fabric_fetcher,
        workspace_name=os.environ["FABRIC_WORKSPACE_NAME"],
        lakehouse=os.environ["FABRIC_LAKEHOUSE_NAME"],
        workspace_id=os.environ["FABRIC_WORKSPACE_ID"],
        lakehouse_id=os.environ["FABRIC_LAKEHOUSE_ID"],
    )


def purge_local_table(lakehouse: LocalLakehouse, name: str) -> None:
    shutil.rmtree(lakehouse._table_dir(name), ignore_errors=True)
    lakehouse._metadata.remove(lakehouse._table_key(name))


@pytest.fixture
def clean_integration_table(fabric_lakehouse):
    purge_local_table(fabric_lakehouse, INTEGRATION_TABLE)
    yield
    purge_local_table(fabric_lakehouse, INTEGRATION_TABLE)


@pytest.fixture
def expected_pandas() -> pd.DataFrame:
    return pd.DataFrame(EXPECTED_ROWS)


@pytest.fixture
def local_row_pandas() -> pd.DataFrame:
    return pd.DataFrame({"id": [99], "name": ["Z"], "value": [0.0]})


@pytest.fixture(params=["pandas", "polars"])
def df_kind(request):
    return request.param
