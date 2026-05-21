from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyspark.sql import DataFrame as SparkDataFrame
else:
    try:
        from pyspark.sql import DataFrame as SparkDataFrame
    except ImportError:
        SparkDataFrame = Any


def spark_dataframe_type() -> type:
    from pyspark.sql import DataFrame as SparkDataFrame

    return SparkDataFrame


def get_or_create_spark_session():
    from pyspark.sql import SparkSession

    return SparkSession.builder.getOrCreate()


def spark_import_error() -> ImportError:
    return ImportError(
        "PySpark is not installed. Use as_='pandas' or as_='polars' locally, "
        "or run in a Microsoft Fabric notebook where Spark is provided by the runtime."
    )
