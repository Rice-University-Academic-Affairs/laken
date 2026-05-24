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

    def write_table(self, df: InputFrame, name: str, *, mode: WriteMode = "overwrite") -> None: ...
