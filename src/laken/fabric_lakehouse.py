from __future__ import annotations

import os

from laken.frames import from_spark, to_spark
from laken.logger import ensure_logging, logger
from laken.spark_runtime import get_or_create_spark_session
from laken.table_names import (
    TableRef,
    format_table_name,
    is_four_part_table_name,
    resolve_table_ref,
    to_spark_table_name,
)
from laken.types import DataFrameTypeName, InputFrame, OutputFrame, WriteMode


class FabricLakehouse:
    def __init__(
        self,
        lakehouse: str | None = None,
        workspace_id: str | None = None,
        workspace_name: str | None = None,
        lakehouse_id: str | None = None,
    ):
        ensure_logging()
        nu = self._notebookutils()
        ctx = nu.runtime.context
        self._explicit_lakehouse = lakehouse is not None
        self._lakehouse = lakehouse or ctx.get("defaultLakehouseName")
        self._workspace_id = workspace_id or ctx.get("currentWorkspaceId")
        self._workspace_name = workspace_name or ctx.get("currentWorkspaceName")
        self._lakehouse_id = lakehouse_id or os.getenv("FABRIC_LAKEHOUSE_ID")
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

    def load_table_from_warehouse(
        self,
        table_name: str,
        warehouse_name: str,
        *,
        schema: str | None = "dbo",
        workspace_id: str | None = None,
        frame_type: DataFrameTypeName = "spark",
    ) -> OutputFrame:
        warehouse_table = self._resolve_warehouse_table_name(table_name, warehouse_name, schema)
        logger.debug("Loading warehouse table %s via synapsesql", warehouse_table)
        constants = _fabric_constants()
        spark_df = (
            self._spark()
            .read.option(
                constants.WorkspaceId,
                self._resolve_warehouse_workspace_id(workspace_id),
            )
            .synapsesql(warehouse_table)
        )
        return from_spark(spark_df, frame_type)

    def write_table(self, df: InputFrame, name: str, *, mode: WriteMode = "overwrite") -> None:
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

    def _table_ref(self, name: str) -> TableRef:
        ref = resolve_table_ref(
            name,
            workspace_name=self._workspace_name,
            workspace_id=self._workspace_id,
            lakehouse_name=self._lakehouse,
            lakehouse_id=self._lakehouse_id,
        )
        return TableRef(
            schema=ref.schema,
            table=ref.table,
            workspace=ref.workspace or self._workspace_name,
            lakehouse=ref.lakehouse or self._lakehouse,
        )

    def _resolve_table_name(self, name: str) -> str:
        stripped = name.strip()
        if is_four_part_table_name(stripped):
            return stripped
        if self._explicit_lakehouse:
            self._require_cross_lakehouse_context()
        ref = self._table_ref(stripped)
        return to_spark_table_name(ref, explicit_lakehouse=self._explicit_lakehouse)

    def _spark(self):
        return get_or_create_spark_session()

    def _resolve_warehouse_workspace_id(self, workspace_id: str | None) -> str:
        resolved = workspace_id if workspace_id is not None else self._workspace_id
        if resolved is None:
            raise ValueError("warehouse reads require: workspace_id")
        return resolved

    def _resolve_warehouse_table_name(
        self, table_name: str, warehouse_name: str, schema: str | None
    ) -> str:
        return ".".join(part for part in [warehouse_name, schema, table_name] if part)

    def _notebookutils(self):
        import notebookutils

        return notebookutils

    def _require_cross_lakehouse_context(self) -> None:
        missing = []
        if not self._lakehouse:
            missing.append("lakehouse")
        if not self._lakehouse_id:
            missing.append("lakehouse_id")
        if not self._workspace_id:
            missing.append("workspace_id")
        if not self._workspace_name:
            missing.append("workspace_name")
        if missing:
            raise ValueError(f"cross-lakehouse operations require: {', '.join(missing)}")

def _fabric_constants():
    __import__("com.microsoft.spark.fabric")
    from com.microsoft.spark.fabric.Constants import Constants

    return Constants
