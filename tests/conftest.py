import pandas as pd
import polars as pl
import pytest

from laken import LocalLakehouse


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
