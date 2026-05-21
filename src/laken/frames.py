import pandas as pd
import polars as pl
import pyarrow as pa
from pyarrow import Table as ArrowTable

from laken._spark import get_or_create_spark_session, spark_dataframe_type, spark_import_error
from laken.types import DfKind, InputFrame, OutputFrame


def kind_of(df: InputFrame) -> DfKind:
    if isinstance(df, pd.DataFrame):
        return "pandas"
    if isinstance(df, pl.DataFrame):
        return "polars"
    try:
        spark_df_type = spark_dataframe_type()
    except ImportError:
        pass
    else:
        if isinstance(df, spark_df_type):
            return "spark"
    raise TypeError(f"unsupported dataframe type: {type(df).__name__}")


def to_arrow(df: InputFrame) -> ArrowTable:
    kind = kind_of(df)
    if kind == "pandas":
        return pa.Table.from_pandas(df)
    if kind == "polars":
        return df.to_arrow()
    return pa.Table.from_pandas(df.toPandas())


def from_arrow(
    table: ArrowTable,
    as_: DfKind,
    spark=None,
) -> OutputFrame:
    if as_ == "pandas":
        return table.to_pandas()
    if as_ == "polars":
        return pl.from_arrow(table)
    try:
        if spark is None:
            spark = get_or_create_spark_session()
        return spark.createDataFrame(table.to_pandas())
    except ImportError as err:
        raise spark_import_error() from err


def to_spark(df: InputFrame, spark) -> OutputFrame:
    kind = kind_of(df)
    if kind == "spark":
        return df
    if kind == "pandas":
        return spark.createDataFrame(df)
    return spark.createDataFrame(df.to_pandas())


def from_spark(spark_df, as_: DfKind) -> OutputFrame:
    if as_ == "spark":
        return spark_df
    if as_ == "pandas":
        return spark_df.toPandas()
    return pl.from_pandas(spark_df.toPandas())
