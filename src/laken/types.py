from typing import Literal

import pandas as pd
import polars as pl
from pyspark.sql import DataFrame as SparkDataFrame

DfKind = Literal["spark", "pandas", "polars"]
WriteMode = Literal["overwrite", "append"]

InputFrame = pd.DataFrame | pl.DataFrame | SparkDataFrame
OutputFrame = InputFrame
