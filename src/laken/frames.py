import pandas as pd
import polars as pl
import pyarrow as pa
from pyarrow import Table as ArrowTable

from laken.spark_runtime import (
    get_or_create_spark_session,
    spark_dataframe_type,
    spark_import_error,
)
from laken.types import DataFrameTypeName, InputFrame, OutputFrame


def dataframe_kind(df: InputFrame) -> DataFrameTypeName:
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
    kind = dataframe_kind(df)
    if kind == "pandas":
        return pa.Table.from_pandas(df)
    if kind == "polars":
        return df.to_arrow()
    to_arrow_fn = getattr(df, "toArrow", None)
    if callable(to_arrow_fn):
        return to_arrow_fn()
    return pa.Table.from_pandas(df.toPandas())


def from_arrow(
    table: ArrowTable,
    frame_type: DataFrameTypeName,
    spark=None,
) -> OutputFrame:
    if frame_type == "pandas":
        return table.to_pandas()
    if frame_type == "polars":
        return pl.from_arrow(table)
    try:
        if spark is None:
            spark = get_or_create_spark_session()
        try:
            return spark.createDataFrame(table)
        except TypeError:
            return spark.createDataFrame(table.to_pandas())
    except ImportError as err:
        raise spark_import_error() from err


def to_spark(df: InputFrame, spark) -> OutputFrame:
    kind = dataframe_kind(df)
    if kind == "spark":
        return df
    if kind == "pandas":
        return spark.createDataFrame(df)
    try:
        return spark.createDataFrame(df.to_arrow())
    except TypeError:
        return spark.createDataFrame(df.to_pandas())


def from_spark(spark_df, frame_type: DataFrameTypeName) -> OutputFrame:
    if frame_type == "spark":
        return spark_df
    if frame_type == "pandas":
        return spark_df.toPandas()
    to_arrow_fn = getattr(spark_df, "toArrow", None)
    if callable(to_arrow_fn):
        return pl.from_arrow(to_arrow_fn())
    return pl.from_pandas(spark_df.toPandas())
