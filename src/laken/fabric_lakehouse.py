from __future__ import annotations

from laken.frames import from_spark, to_spark
from laken.logger import ensure_logging, logger
from laken.spark_runtime import get_or_create_spark_session
from laken.table_names import parse_table_ref, spark_table_name
from laken.types import DataFrameTypeName, InputFrame, OutputFrame, WriteMode


class FabricLakehouse:
    def __init__(self) -> None:
        ensure_logging()
        nu = self._notebookutils()
        ctx = nu.runtime.context
        self._lakehouse = ctx.get("defaultLakehouseName")
        self._workspace_id = ctx.get("currentWorkspaceId")
        self._workspace_name = ctx.get("currentWorkspaceName")
        logger.debug(
            "FabricLakehouse ready (lakehouse=%s, workspace=%s)",
            self._lakehouse,
            self._workspace_name,
        )

    def read_table(
        self,
        name: str,
        *,
        frame_type: DataFrameTypeName = "spark",
        max_mirror_mb: int | None = None,
        max_sample_rows: int | None = None,
    ) -> OutputFrame:
        _ = max_mirror_mb, max_sample_rows
        resolved = self._resolve_table_name(name)
        logger.debug("Reading %s from Fabric table %s", name, resolved)
        spark = self._spark()
        spark_df = spark.read.table(resolved)
        return from_spark(spark_df, frame_type)

    def write_table(self, df: InputFrame, name: str, *, mode: WriteMode = "overwrite") -> None:
        spark = self._spark()
        to_spark(df, spark).write.mode(mode).format("delta").saveAsTable(
            self._resolve_table_name(name)
        )

    def _resolve_table_name(self, name: str) -> str:
        return spark_table_name(parse_table_ref(name))

    def _spark(self):
        return get_or_create_spark_session()

    def _notebookutils(self):
        import notebookutils

        return notebookutils
