from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from laken.frames import from_arrow, kind_of, to_arrow


class TestKindOf:
    def test_pandas(self, sample_pandas):
        assert kind_of(sample_pandas) == "pandas"

    def test_polars(self, sample_polars):
        assert kind_of(sample_polars) == "polars"

    def test_unknown_raises(self):
        with pytest.raises(TypeError):
            kind_of([1, 2, 3])


class TestArrowRoundtrip:
    @pytest.mark.parametrize("kind", ["pandas", "polars"])
    def test_roundtrip(self, kind, sample_pandas, sample_polars):
        samples = {"pandas": sample_pandas, "polars": sample_polars}
        df = samples[kind]
        result = from_arrow(to_arrow(df), kind)
        assert kind_of(result) == kind
        if kind == "pandas":
            assert len(result) == 2
        else:
            assert result.height == 2


class TestFromArrowSpark:
    @patch("laken.frames.get_or_create_spark_session")
    def test_create_dataframe_called(self, mock_get_spark):
        mock_spark = MagicMock()
        mock_get_spark.return_value = mock_spark
        mock_spark.createDataFrame.return_value = MagicMock()
        table = to_arrow(pd.DataFrame({"id": [1], "value": ["a"]}))
        result = from_arrow(table, "spark")
        mock_spark.createDataFrame.assert_called_once()
        assert isinstance(result, MagicMock)
