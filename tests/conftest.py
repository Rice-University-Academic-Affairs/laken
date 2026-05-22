import logging

import pandas as pd
import polars as pl
import pytest

from laken import LocalLakehouse

_FABRIC_ENV_VARS = (
    "FABRIC_WORKSPACE_NAME",
    "FABRIC_LAKEHOUSE_NAME",
    "FABRIC_WORKSPACE_ID",
    "FABRIC_LAKEHOUSE_ID",
    "FABRIC_ENVIRONMENT_ID",
    "AZURE_TENANT_ID",
    "AZURE_CLIENT_ID",
    "AZURE_CLIENT_SECRET",
)


@pytest.fixture(autouse=True)
def isolate_unit_test_fabric_env(request, monkeypatch):
    if request.node.get_closest_marker("integration"):
        return
    for name in _FABRIC_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def capture_laken_logs(caplog):
    caplog.set_level(logging.INFO, logger="laken")
    for handler in list(logging.getLogger("laken").handlers):
        if type(handler) is logging.StreamHandler:
            logging.getLogger("laken").removeHandler(handler)
    return caplog


@pytest.fixture
def lakehouse(tmp_path):
    return LocalLakehouse(root=tmp_path / "lakehouse")


@pytest.fixture
def sample_pandas():
    return pd.DataFrame({"id": [1, 2], "value": ["a", "b"]})


@pytest.fixture
def sample_polars():
    return pl.DataFrame({"id": [1, 2], "value": ["a", "b"]})


@pytest.fixture(params=["pandas", "polars"])
def df_kind(request):
    return request.param


@pytest.fixture
def sample_df(df_kind, sample_pandas, sample_polars):
    if df_kind == "pandas":
        return sample_pandas
    return sample_polars
