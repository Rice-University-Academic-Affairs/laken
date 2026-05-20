from typing import Literal, overload

import pandas as pd
import polars as pl
from pyspark.sql import DataFrame as SparkDataFrame
from pyspark.sql import SparkSession

from laken.frames import from_spark, to_spark
from laken.paths import format_table_name, parse_table_name
from laken.types import DfKind, InputFrame, WriteMode


def _get_current_spark_session() -> SparkSession:
    return SparkSession.builder.getOrCreate()


class FabricLakehouse:
    def __init__(
        self,
        lakehouse: str | None = None,
        workspace_id: str | None = None,
        workspace_name: str | None = None,
    ):
        nu = self._notebookutils()
        ctx = nu.runtime.context
        self._explicit_lakehouse = lakehouse is not None
        self._lakehouse = lakehouse or ctx.get("defaultLakehouseName")
        self._workspace_id = workspace_id or ctx.get("currentWorkspaceId")
        self._workspace_name = workspace_name or ctx["currentWorkspaceName"]

    def _spark(self) -> SparkSession:
        return _get_current_spark_session()

    def _notebookutils(self):
        import notebookutils

        return notebookutils

    def _require_cross_lakehouse_context(self) -> None:
        missing = []
        if not self._lakehouse:
            missing.append("lakehouse")
        if not self._workspace_id:
            missing.append("workspace_id")
        if not self._workspace_name:
            missing.append("workspace_name")
        if missing:
            raise ValueError(
                f"cross-lakehouse operations require: {', '.join(missing)}"
            )

    def _abfss_root(self) -> str:
        self._require_cross_lakehouse_context()
        return (
            f"abfss://{self._workspace_name}@onelake.dfs.fabric.microsoft.com/"
            f"{self._lakehouse}.Lakehouse/"
        )

    def _resolve_table_name(self, name: str) -> str:
        schema, table = parse_table_name(name)
        if not self._explicit_lakehouse:
            return format_table_name(schema, table)
        self._require_cross_lakehouse_context()
        return f"{self._workspace_name}.{self._lakehouse}.{schema}.{table}"

    def _file_path(self, path: str) -> str:
        normalized = path.replace("\\", "/").lstrip("/")
        if not self._explicit_lakehouse:
            return f"Files/{normalized}" if normalized else "Files"
        return f"{self._abfss_root()}Files/{normalized}"

    @overload
    def read_table(self, name: str, *, as_: Literal["spark"] = "spark") -> SparkDataFrame: ...

    @overload
    def read_table(self, name: str, *, as_: Literal["pandas"]) -> pd.DataFrame: ...

    @overload
    def read_table(self, name: str, *, as_: Literal["polars"]) -> pl.DataFrame: ...

    def read_table(
        self, name: str, *, as_: DfKind = "spark"
    ) -> SparkDataFrame | pd.DataFrame | pl.DataFrame:
        spark = self._spark()
        spark_df = spark.read.table(self._resolve_table_name(name))
        return from_spark(spark_df, as_)

    def write_table(
        self, df: InputFrame, name: str, *, mode: WriteMode = "overwrite"
    ) -> None:
        spark = self._spark()
        to_spark(df, spark).write.mode(mode).format("delta").saveAsTable(
            self._resolve_table_name(name)
        )

    def list_tables(self) -> list[str]:
        nu = self._notebookutils()
        tables = nu.lakehouse.listTables(
            lakehouse=self._lakehouse or "",
            workspaceId=self._workspace_id or "",
        )
        result: list[str] = []
        for entry in tables:
            schema = getattr(entry, "schema", None) or getattr(entry, "schemaName", None)
            table = getattr(entry, "name", None) or getattr(entry, "tableName", None)
            if schema and table:
                result.append(format_table_name(schema, table))
            elif table:
                result.append(format_table_name("dbo", table))
        return sorted(result)

    def table_exists(self, name: str) -> bool:
        spark = self._spark()
        return spark.catalog.tableExists(self._resolve_table_name(name))

    def drop_table(self, name: str) -> None:
        spark = self._spark()
        spark.catalog.dropTable(self._resolve_table_name(name), ignoreIfNotExists=True)

    @overload
    def read_file(self, path: str, *, as_: Literal["spark"] = "spark") -> SparkDataFrame: ...

    @overload
    def read_file(self, path: str, *, as_: Literal["pandas"]) -> pd.DataFrame: ...

    @overload
    def read_file(self, path: str, *, as_: Literal["polars"]) -> pl.DataFrame: ...

    def read_file(
        self, path: str, *, as_: DfKind = "spark"
    ) -> SparkDataFrame | pd.DataFrame | pl.DataFrame:
        spark = self._spark()
        spark_df = spark.read.parquet(self._file_path(path))
        return from_spark(spark_df, as_)

    def write_file(
        self, df: InputFrame, path: str, *, mode: WriteMode = "overwrite"
    ) -> None:
        spark = self._spark()
        to_spark(df, spark).write.mode(mode).format("parquet").save(
            self._file_path(path)
        )

    def list_files(self, path: str = "") -> list[str]:
        nu = self._notebookutils()
        entries = nu.fs.ls(self._file_path(path))
        return [entry.name for entry in entries]

    def file_exists(self, path: str) -> bool:
        nu = self._notebookutils()
        return nu.fs.exists(self._file_path(path))

    def delete_file(self, path: str) -> None:
        nu = self._notebookutils()
        nu.fs.rm(self._file_path(path), recurse=False)
