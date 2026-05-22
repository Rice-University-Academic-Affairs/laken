from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from laken.frames import from_spark, to_arrow, to_spark
from laken.logger import ensure_logging, logger
from laken.spark_runtime import get_or_create_spark_session
from laken.table_names import (
    TableRef,
    format_table_name,
    is_four_part_table_name,
    resolve_table_ref,
    to_spark_table_name,
)
from laken.types import DataFrameTypeName, FileWrite, InputFrame, OutputFrame, WriteMode


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

    def read_file(self, path: str) -> bytes:
        resolved_path = self._file_path(path)
        logger.debug("Reading Fabric file %s", resolved_path)
        nu = self._notebookutils()
        return _read_fabric_file_bytes(nu, resolved_path, suffix=Path(path).suffix.lower())

    def write_file(self, data: FileWrite, path: str, *, mode: WriteMode = "overwrite") -> None:
        resolved_path = self._file_path(path)
        nu = self._notebookutils()
        if isinstance(data, bytes):
            write_mode = "ab" if mode == "append" and nu.fs.exists(resolved_path) else "wb"
            with nu.fs.open(resolved_path, write_mode) as handle:
                handle.write(data)
            return
        suffix = Path(path).suffix.lower()
        if suffix == ".csv":
            _write_fabric_csv(nu, resolved_path, to_arrow(data), mode=mode)
            return
        if suffix == ".parquet":
            _write_fabric_parquet(nu, resolved_path, to_arrow(data), mode=mode)
            return
        raise ValueError(f"unsupported file extension for dataframe write: {suffix}")

    def file_exists(self, path: str) -> bool:
        nu = self._notebookutils()
        resolved_path = self._file_path(path)
        if nu.fs.exists(resolved_path):
            return True
        suffix = Path(path).suffix.lower()
        return bool(_fabric_spark_part_paths(nu, resolved_path, suffix=suffix))

    def delete_file(self, path: str) -> None:
        nu = self._notebookutils()
        resolved_path = self._file_path(path)
        suffix = Path(path).suffix.lower()
        recurse = bool(_fabric_spark_part_paths(nu, resolved_path, suffix=suffix))
        nu.fs.rm(resolved_path, recurse=recurse)

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

    def _file_path(self, path: str) -> str:
        normalized = path.replace("\\", "/").lstrip("/")
        if not self._explicit_lakehouse:
            return f"Files/{normalized}" if normalized else "Files"
        return f"{self._abfss_root()}Files/{normalized}"

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

    def _abfss_root(self) -> str:
        self._require_cross_lakehouse_context()
        return (
            f"abfss://{self._workspace_id}@onelake.dfs.fabric.microsoft.com/{self._lakehouse_id}/"
        )


def _fabric_entry_name(entry) -> str:
    name = getattr(entry, "name", None)
    if name:
        return name
    path = getattr(entry, "path", None)
    if path:
        return Path(str(path)).name
    return str(entry)


def _fabric_ls(nu, path: str) -> list:
    return nu.fs.ls(path)


def _fabric_spark_part_paths(nu, resolved_path: str, *, suffix: str) -> list[str]:
    if not nu.fs.exists(resolved_path):
        return []
    try:
        entries = _fabric_ls(nu, resolved_path)
    except Exception:
        return []
    part_names = sorted(
        name
        for name in (_fabric_entry_name(entry) for entry in entries)
        if name.startswith("part-") and name.endswith(suffix)
    )
    if not part_names:
        return []
    base = resolved_path.rstrip("/")
    return [f"{base}/{name}" for name in part_names]


def _read_fabric_file_bytes(nu, resolved_path: str, *, suffix: str) -> bytes:
    if suffix == ".parquet":
        return _read_fabric_parquet_bytes(nu, resolved_path)
    return _read_fabric_flat_or_part_bytes(nu, resolved_path, suffix=suffix)


def _read_fabric_flat_or_part_bytes(nu, resolved_path: str, *, suffix: str) -> bytes:
    part_paths = _fabric_spark_part_paths(nu, resolved_path, suffix=suffix)
    if part_paths:
        with nu.fs.open(part_paths[0], "rb") as handle:
            return handle.read()
    if not nu.fs.exists(resolved_path):
        raise FileNotFoundError(f"file not found: {resolved_path}")
    with nu.fs.open(resolved_path, "rb") as handle:
        return handle.read()


def _read_fabric_parquet_bytes(nu, resolved_path: str) -> bytes:
    part_paths = _fabric_spark_part_paths(nu, resolved_path, suffix=".parquet")
    if part_paths:
        if len(part_paths) == 1:
            with nu.fs.open(part_paths[0], "rb") as handle:
                return handle.read()
        tables = []
        for part_path in part_paths:
            with nu.fs.open(part_path, "rb") as handle:
                tables.append(pq.read_table(pa.BufferReader(handle.read())))
        sink = pa.BufferOutputStream()
        pq.write_table(pa.concat_tables(tables), sink)
        return sink.getvalue().to_pybytes()
    if not nu.fs.exists(resolved_path):
        raise FileNotFoundError(f"file not found: {resolved_path}")
    with nu.fs.open(resolved_path, "rb") as handle:
        return handle.read()


def _write_fabric_parquet(
    nu,
    resolved_path: str,
    arrow_table: pa.Table,
    *,
    mode: WriteMode,
) -> None:
    if mode == "append" and nu.fs.exists(resolved_path):
        existing = pq.read_table(pa.BufferReader(_read_fabric_parquet_bytes(nu, resolved_path)))
        arrow_table = pa.concat_tables([existing, arrow_table])
    if nu.fs.exists(resolved_path):
        nu.fs.rm(resolved_path, recurse=True)
    sink = pa.BufferOutputStream()
    pq.write_table(arrow_table, sink)
    with nu.fs.open(resolved_path, "wb") as handle:
        handle.write(sink.getvalue().to_pybytes())


def _write_fabric_csv(
    nu,
    resolved_path: str,
    arrow_table: pa.Table,
    *,
    mode: WriteMode,
) -> None:
    if mode == "append" and nu.fs.exists(resolved_path):
        raw = _read_fabric_file_bytes(nu, resolved_path, suffix=".csv")
        existing = pacsv.read_csv(BytesIO(raw))
        arrow_table = pa.concat_tables([existing, arrow_table])
    sink = pa.BufferOutputStream()
    pacsv.write_csv(arrow_table, sink)
    with nu.fs.open(resolved_path, "wb") as handle:
        handle.write(sink.getvalue().to_pybytes())


def _fabric_constants():
    __import__("com.microsoft.spark.fabric")
    from com.microsoft.spark.fabric.Constants import Constants

    return Constants
