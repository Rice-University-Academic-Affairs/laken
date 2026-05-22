from __future__ import annotations

from typing import Protocol, runtime_checkable

from laken.types import DataFrameTypeName, InputFrame, OutputFrame, WriteMode


@runtime_checkable
class LakehouseProtocol(Protocol):
    def read_table(
        self,
        name: str,
        *,
        frame_type: DataFrameTypeName | None = None,
        max_mirror_mb: int | None = None,
        max_sample_rows: int | None = None,
    ) -> OutputFrame: ...

    def load_table_from_warehouse(
        self,
        table_name: str,
        warehouse_name: str,
        *,
        schema: str | None = "dbo",
        workspace_id: str | None = None,
        frame_type: DataFrameTypeName | None = None,
    ) -> OutputFrame: ...

    def write_table(self, df: InputFrame, name: str, *, mode: WriteMode = "overwrite") -> None: ...

    def list_tables(self) -> list[str]: ...

    def table_exists(self, name: str) -> bool: ...

    def drop_table(self, name: str) -> None: ...

    def read_file(self, path: str) -> bytes: ...

    def write_file(self, df: InputFrame, path: str, *, mode: WriteMode = "overwrite") -> None: ...

    def file_exists(self, path: str) -> bool: ...

    def delete_file(self, path: str) -> None: ...
