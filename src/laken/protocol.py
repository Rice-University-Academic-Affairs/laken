from __future__ import annotations

from typing import Literal, Protocol, overload, runtime_checkable

import pandas as pd
import polars as pl

from laken._spark import SparkDataFrame
from laken.types import DfKind, InputFrame, OutputFrame, WriteMode


@runtime_checkable
class LakehouseProtocol(Protocol):
    @overload
    def read_table(
        self,
        name: str,
        *,
        as_: Literal["pandas"] = "pandas",
        max_mirror_mb: int | None = None,
        max_sample_rows: int | None = None,
    ) -> pd.DataFrame: ...

    @overload
    def read_table(
        self,
        name: str,
        *,
        as_: Literal["spark"],
        max_mirror_mb: int | None = None,
        max_sample_rows: int | None = None,
    ) -> SparkDataFrame: ...

    @overload
    def read_table(
        self,
        name: str,
        *,
        as_: Literal["polars"],
        max_mirror_mb: int | None = None,
        max_sample_rows: int | None = None,
    ) -> pl.DataFrame: ...

    def read_table(
        self,
        name: str,
        *,
        as_: DfKind | None = None,
        max_mirror_mb: int | None = None,
        max_sample_rows: int | None = None,
    ) -> OutputFrame: ...

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
    ) -> OutputFrame: ...

    def write_table(self, df: InputFrame, name: str, *, mode: WriteMode = "overwrite") -> None: ...

    def list_tables(self) -> list[str]: ...

    def table_exists(self, name: str) -> bool: ...

    def drop_table(self, name: str) -> None: ...

    @overload
    def read_file(self, path: str, *, as_: Literal["pandas"] = "pandas") -> pd.DataFrame: ...

    @overload
    def read_file(self, path: str, *, as_: Literal["spark"]) -> SparkDataFrame: ...

    @overload
    def read_file(self, path: str, *, as_: Literal["polars"]) -> pl.DataFrame: ...

    def read_file(self, path: str, *, as_: DfKind | None = None) -> OutputFrame: ...

    def write_file(self, df: InputFrame, path: str, *, mode: WriteMode = "overwrite") -> None: ...

    def list_files(self, path: str = "") -> list[str]: ...

    def file_exists(self, path: str) -> bool: ...

    def delete_file(self, path: str) -> None: ...
