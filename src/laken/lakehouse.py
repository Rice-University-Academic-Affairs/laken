from __future__ import annotations

import os
from typing import Literal, overload

import pandas as pd
import polars as pl

from laken.lakehouse_protocol import LakehouseProtocol
from laken.local_lakehouse import LocalLakehouse
from laken.spark_runtime import SparkDataFrame
from laken.types import DfKind, InputFrame, OutputFrame, WriteMode
from laken.workspace import DEFAULT_MAX_MIRROR_MB, DEFAULT_MAX_SAMPLE_ROWS, FabricTableFetcher


def _is_fabric_context() -> bool:
    try:
        import notebookutils
    except ImportError:
        return False
    try:
        context = notebookutils.runtime.context
    except Exception:
        return False
    get = getattr(context, "get", None)
    if not callable(get):
        return False
    return bool(get("currentWorkspaceId") or get("currentWorkspaceName"))


def _default_df_kind(implementation: LakehouseProtocol) -> DfKind:
    from laken.fabric_lakehouse import FabricLakehouse

    if isinstance(implementation, FabricLakehouse):
        return "spark"
    return "pandas"


class Lakehouse:
    def __init__(
        self,
        *,
        root: str | os.PathLike = ".laken/workspace",
        lakehouse: str | None = None,
        workspace_id: str | None = None,
        workspace_name: str | None = None,
        metadata_path: str | os.PathLike | None = None,
        fabric_fetcher: FabricTableFetcher | None = None,
        max_mirror_mb: int = DEFAULT_MAX_MIRROR_MB,
        max_sample_rows: int = DEFAULT_MAX_SAMPLE_ROWS,
    ):
        if _is_fabric_context():
            from laken.fabric_lakehouse import FabricLakehouse

            self._implementation: LakehouseProtocol = FabricLakehouse(
                lakehouse=lakehouse,
                workspace_id=workspace_id,
                workspace_name=workspace_name,
            )
        else:
            self._implementation = LocalLakehouse(
                root=root,
                lakehouse=lakehouse,
                workspace_id=workspace_id,
                workspace_name=workspace_name,
                metadata_path=metadata_path,
                fabric_fetcher=fabric_fetcher,
                max_mirror_mb=max_mirror_mb,
                max_sample_rows=max_sample_rows,
            )

    @overload
    def read_table(
        self,
        name: str,
        *,
        frame_type: Literal["pandas"] = "pandas",
        max_mirror_mb: int | None = None,
        max_sample_rows: int | None = None,
    ) -> pd.DataFrame: ...

    @overload
    def read_table(
        self,
        name: str,
        *,
        frame_type: Literal["spark"],
        max_mirror_mb: int | None = None,
        max_sample_rows: int | None = None,
    ) -> SparkDataFrame: ...

    @overload
    def read_table(
        self,
        name: str,
        *,
        frame_type: Literal["polars"],
        max_mirror_mb: int | None = None,
        max_sample_rows: int | None = None,
    ) -> pl.DataFrame: ...

    def read_table(
        self,
        name: str,
        *,
        frame_type: DfKind | None = None,
        max_mirror_mb: int | None = None,
        max_sample_rows: int | None = None,
    ) -> OutputFrame:
        kind = _default_df_kind(self._implementation) if frame_type is None else frame_type
        return self._implementation.read_table(
            name,
            frame_type=kind,
            max_mirror_mb=max_mirror_mb,
            max_sample_rows=max_sample_rows,
        )

    @overload
    def load_table_from_warehouse(
        self,
        table_name: str,
        warehouse_name: str,
        *,
        schema: str | None = "dbo",
        workspace_id: str | None = None,
        frame_type: Literal["pandas"] = "pandas",
    ) -> pd.DataFrame: ...

    @overload
    def load_table_from_warehouse(
        self,
        table_name: str,
        warehouse_name: str,
        *,
        schema: str | None = "dbo",
        workspace_id: str | None = None,
        frame_type: Literal["spark"],
    ) -> SparkDataFrame: ...

    @overload
    def load_table_from_warehouse(
        self,
        table_name: str,
        warehouse_name: str,
        *,
        schema: str | None = "dbo",
        workspace_id: str | None = None,
        frame_type: Literal["polars"],
    ) -> pl.DataFrame: ...

    def load_table_from_warehouse(
        self,
        table_name: str,
        warehouse_name: str,
        *,
        schema: str | None = "dbo",
        workspace_id: str | None = None,
        frame_type: DfKind | None = None,
    ) -> OutputFrame:
        kind = _default_df_kind(self._implementation) if frame_type is None else frame_type
        return self._implementation.load_table_from_warehouse(
            table_name,
            warehouse_name,
            schema=schema,
            workspace_id=workspace_id,
            frame_type=kind,
        )

    def write_table(self, df: InputFrame, name: str, *, mode: WriteMode = "overwrite") -> None:
        self._implementation.write_table(df, name, mode=mode)

    def list_tables(self) -> list[str]:
        return self._implementation.list_tables()

    def table_exists(self, name: str) -> bool:
        return self._implementation.table_exists(name)

    def drop_table(self, name: str) -> None:
        self._implementation.drop_table(name)

    @overload
    def read_file(self, path: str, *, frame_type: Literal["pandas"] = "pandas") -> pd.DataFrame: ...

    @overload
    def read_file(self, path: str, *, frame_type: Literal["spark"]) -> SparkDataFrame: ...

    @overload
    def read_file(self, path: str, *, frame_type: Literal["polars"]) -> pl.DataFrame: ...

    def read_file(self, path: str, *, frame_type: DfKind | None = None) -> OutputFrame:
        kind = _default_df_kind(self._implementation) if frame_type is None else frame_type
        return self._implementation.read_file(path, frame_type=kind)

    def write_file(self, df: InputFrame, path: str, *, mode: WriteMode = "overwrite") -> None:
        self._implementation.write_file(df, path, mode=mode)

    def list_files(self, path: str = "") -> list[str]:
        return self._implementation.list_files(path)

    def file_exists(self, path: str) -> bool:
        return self._implementation.file_exists(path)

    def delete_file(self, path: str) -> None:
        return self._implementation.delete_file(path)
