from typing import Any, Literal

import pandas as pd
import polars as pl

DfKind = Literal["spark", "pandas", "polars"]
WriteMode = Literal["overwrite", "append"]

InputFrame = pd.DataFrame | pl.DataFrame | Any
OutputFrame = InputFrame
