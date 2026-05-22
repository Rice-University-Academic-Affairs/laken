from typing import TYPE_CHECKING, Literal

import pandas as pd
import polars as pl

DfKind = Literal["spark", "pandas", "polars"]
WriteMode = Literal["overwrite", "append"]

if TYPE_CHECKING:
    from pyspark.sql import DataFrame as SparkDataFrame

    InputFrame = pd.DataFrame | pl.DataFrame | SparkDataFrame
    OutputFrame = pd.DataFrame | pl.DataFrame | SparkDataFrame
else:
    InputFrame = pd.DataFrame | pl.DataFrame | object
    OutputFrame = pd.DataFrame | pl.DataFrame | object
