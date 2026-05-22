import laken._env  # noqa: F401
from laken.fabric import FabricLakehouse
from laken.lakehouse import Lakehouse
from laken.local import LocalLakehouse
from laken.protocol import LakehouseProtocol
from laken.types import DfKind, InputFrame, OutputFrame, WriteMode


def read_table(
    name: str,
    *,
    as_: DfKind | None = None,
    max_mirror_mb: int | None = None,
    max_sample_rows: int | None = None,
) -> OutputFrame:
    return Lakehouse().read_table(
        name,
        as_=as_,
        max_mirror_mb=max_mirror_mb,
        max_sample_rows=max_sample_rows,
    )


def write_table(name: str, df: InputFrame, *, mode: WriteMode = "overwrite") -> None:
    Lakehouse().write_table(df, name, mode=mode)


__all__ = [
    "FabricLakehouse",
    "Lakehouse",
    "LakehouseProtocol",
    "LocalLakehouse",
    "read_table",
    "write_table",
]
