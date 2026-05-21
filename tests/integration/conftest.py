import os

import pandas as pd
import polars as pl
import pytest
import requests
from deltalake import write_deltalake

from laken import LocalLakehouse
from laken.onelake_fetcher import (
    OneLakeFabricFetcher,
    _azure_credentials_available,
    _fabric_access_token,
    _lakehouse_root_uri,
    _storage_options,
    default_fabric_fetcher,
)

INTEGRATION_TABLE = "example_integration_test"
INTEGRATION_CSV = "examples/integration_test/example_integration_test.csv"

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


def _integration_fixture_ready(fetcher: OneLakeFabricFetcher) -> bool:
    try:
        return fetcher.fetch_table(INTEGRATION_TABLE).num_rows == len(
            EXPECTED_ROWS
        ) and fetcher.fetch_file(INTEGRATION_CSV).num_rows == len(EXPECTED_ROWS)
    except Exception:
        return False


def _seed_integration_fixtures(fetcher: OneLakeFabricFetcher) -> None:
    if not fetcher._workspace_id or not fetcher._lakehouse_id:
        pytest.skip("Fabric workspace and lakehouse IDs are required for integration fixtures")
    df = pd.DataFrame(EXPECTED_ROWS)
    root = _lakehouse_root_uri(
        fetcher._workspace_name,
        fetcher._lakehouse,
        workspace_id=fetcher._workspace_id,
        lakehouse_id=fetcher._lakehouse_id,
    )
    write_deltalake(
        f"{root}Tables/{INTEGRATION_TABLE}",
        df,
        mode="overwrite",
        storage_options=_storage_options(),
    )
    token = _fabric_access_token()
    headers = {"Authorization": f"Bearer {token}", "x-ms-version": "2021-06-08"}
    for directory in ("Files/examples", "Files/examples/integration_test"):
        url = (
            f"https://onelake.dfs.fabric.microsoft.com/{fetcher._workspace_id}/"
            f"{fetcher._lakehouse_id}/{directory}"
        )
        requests.put(
            url, headers=headers, params={"resource": "directory"}, timeout=60
        ).raise_for_status()
    csv_bytes = df.to_csv(index=False).encode()
    file_url = (
        f"https://onelake.dfs.fabric.microsoft.com/{fetcher._workspace_id}/"
        f"{fetcher._lakehouse_id}/Files/{INTEGRATION_CSV}"
    )
    requests.delete(file_url, headers=headers, params={"recursive": "true"}, timeout=60)
    requests.put(
        file_url, headers=headers, params={"resource": "file"}, timeout=60
    ).raise_for_status()
    requests.patch(
        file_url,
        headers={
            **headers,
            "Content-Type": "application/octet-stream",
            "Content-Length": str(len(csv_bytes)),
        },
        params={"action": "append", "position": "0"},
        data=csv_bytes,
        timeout=120,
    ).raise_for_status()
    requests.patch(
        file_url,
        headers=headers,
        params={"action": "flush", "position": str(len(csv_bytes)), "close": "true"},
        timeout=120,
    ).raise_for_status()


def fabric_credentials_configured() -> bool:
    if not _azure_credentials_available():
        return False
    return bool(os.getenv("FABRIC_WORKSPACE_NAME") and os.getenv("FABRIC_LAKEHOUSE_NAME"))


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
    if not _integration_fixture_ready(fetcher):
        _seed_integration_fixtures(fetcher)
    return fetcher


@pytest.fixture
def fabric_lakehouse(tmp_path, fabric_fetcher) -> LocalLakehouse:
    return LocalLakehouse(
        root=tmp_path / "workspace",
        fabric_fetcher=fabric_fetcher,
        workspace_name=os.environ["FABRIC_WORKSPACE_NAME"],
        lakehouse=os.environ["FABRIC_LAKEHOUSE_NAME"],
        workspace_id=os.getenv("FABRIC_WORKSPACE_ID"),
    )


@pytest.fixture
def clean_integration_table(fabric_lakehouse):
    fabric_lakehouse.drop_table(INTEGRATION_TABLE)
    yield
    fabric_lakehouse.drop_table(INTEGRATION_TABLE)


@pytest.fixture
def expected_pandas() -> pd.DataFrame:
    return pd.DataFrame(EXPECTED_ROWS)


@pytest.fixture
def local_row_pandas() -> pd.DataFrame:
    return pd.DataFrame({"id": [99], "name": ["Z"], "value": [0.0]})


@pytest.fixture(params=["pandas", "polars"])
def df_kind(request):
    return request.param
