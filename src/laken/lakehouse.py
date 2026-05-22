from __future__ import annotations

import os
from typing import Literal, overload

import pandas as pd
import polars as pl

from laken._spark import SparkDataFrame
from laken.local import LocalLakehouse
from laken.onelake_fetcher import default_fabric_fetcher
from laken.protocol import LakehouseProtocol
from laken.types import DfKind, InputFrame, OutputFrame, WriteMode
from laken.workspace import DEFAULT_MAX_SAMPLE_ROWS, MAX_FULL_CACHE_BYTES, FabricTableFetcher


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
    from laken.fabric import FabricLakehouse

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
        max_full_cache_bytes: int = MAX_FULL_CACHE_BYTES,
        max_sample_rows: int = DEFAULT_MAX_SAMPLE_ROWS,
    ):
        if _is_fabric_context():
            from laken.fabric import FabricLakehouse

            self._implementation: LakehouseProtocol = FabricLakehouse(
                lakehouse=lakehouse,
                workspace_id=workspace_id,
                workspace_name=workspace_name,
            )
            return
        resolved_fetcher = fabric_fetcher or default_fabric_fetcher(
            lakehouse=lakehouse,
            workspace_id=workspace_id,
            workspace_name=workspace_name,
        )
        self._implementation = LocalLakehouse(
            root=root,
            lakehouse=lakehouse,
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            metadata_path=metadata_path,
            fabric_fetcher=resolved_fetcher,
            max_full_cache_bytes=max_full_cache_bytes,
            max_sample_rows=max_sample_rows,
        )

    @overload
    def read_table(
        self,
        name: str,
        *,
        as_: Literal["pandas"] = "pandas",
        max_full_cache_bytes: int | None = None,
        max_sample_rows: int | None = None,
    ) -> pd.DataFrame: ...

    @overload
    def read_table(
        self,
        name: str,
        *,
        as_: Literal["spark"],
        max_full_cache_bytes: int | None = None,
        max_sample_rows: int | None = None,
    ) -> SparkDataFrame: ...

    @overload
    def read_table(
        self,
        name: str,
        *,
        as_: Literal["polars"],
        max_full_cache_bytes: int | None = None,
        max_sample_rows: int | None = None,
    ) -> pl.DataFrame: ...

    def read_table(
        self,
        name: str,
        *,
        as_: DfKind | None = None,
        max_full_cache_bytes: int | None = None,
        max_sample_rows: int | None = None,
    ) -> OutputFrame:
        kind = _default_df_kind(self._implementation) if as_ is None else as_
        return self._implementation.read_table(
            name,
            as_=kind,
            max_full_cache_bytes=max_full_cache_bytes,
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
        as_: Literal["pandas"] = "pandas",
    ) -> pd.DataFrame: ...

    @overload
    def load_table_from_warehouse(
        self,
        table_name: str,
        warehouse_name: str,
        *,
        schema: str | None = "dbo",
        workspace_id: str | None = None,
        as_: Literal["spark"],
    ) -> SparkDataFrame: ...

    @overload
    def load_table_from_warehouse(
        self,
        table_name: str,
        warehouse_name: str,
        *,
        schema: str | None = "dbo",
        workspace_id: str | None = None,
        as_: Literal["polars"],
    ) -> pl.DataFrame: ...

    def load_table_from_warehouse(
        self,
        table_name: str,
        warehouse_name: str,
        *,
        schema: str | None = "dbo",
        workspace_id: str | None = None,
        as_: DfKind | None = None,
    ) -> OutputFrame:
        kind = _default_df_kind(self._implementation) if as_ is None else as_
        return self._implementation.load_table_from_warehouse(
            table_name,
            warehouse_name,
            schema=schema,
            workspace_id=workspace_id,
            as_=kind,
        )

    def write_table(self, df: InputFrame, name: str, *, mode: WriteMode = "overwrite") -> None:
        self._implementation.write_table(df, name, mode=mode)

    def list_tables(self) -> list[str]:
        return self._implementation.list_tables()

    def table_exists(self, name: str) -> bool:
        return self._implementation.table_exists(name)

    def drop_table(self, name: str) -> None:
        self._implementation.drop_table(name)

    def refresh_table(self, name: str) -> None:
        refresh = getattr(self._implementation, "refresh_table", None)
        if not callable(refresh):
            raise RuntimeError("refresh_table is only available in local mode")
        refresh(name)

    def reset_table(self, name: str) -> None:
        reset = getattr(self._implementation, "reset_table", None)
        if not callable(reset):
            raise RuntimeError("reset_table is only available in local mode")
        reset(name)

    def status(self) -> list[dict[str, str]]:
        status = getattr(self._implementation, "status", None)
        if not callable(status):
            raise RuntimeError("status is only available in local mode")
        return status()

    @overload
    def read_file(self, path: str, *, as_: Literal["pandas"] = "pandas") -> pd.DataFrame: ...

    @overload
    def read_file(self, path: str, *, as_: Literal["spark"]) -> SparkDataFrame: ...

    @overload
    def read_file(self, path: str, *, as_: Literal["polars"]) -> pl.DataFrame: ...

    def read_file(self, path: str, *, as_: DfKind | None = None) -> OutputFrame:
        kind = _default_df_kind(self._implementation) if as_ is None else as_
        return self._implementation.read_file(path, as_=kind)

    def write_file(self, df: InputFrame, path: str, *, mode: WriteMode = "overwrite") -> None:
        self._implementation.write_file(df, path, mode=mode)

    def list_files(self, path: str = "") -> list[str]:
        return self._implementation.list_files(path)

    def file_exists(self, path: str) -> bool:
        return self._implementation.file_exists(path)

    def delete_file(self, path: str) -> None:
        self._implementation.delete_file(path)
