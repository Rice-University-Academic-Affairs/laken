from laken._env import load_environment
from laken.fabric_lakehouse import FabricLakehouse
from laken.lakehouse import Lakehouse
from laken.lakehouse_protocol import LakehouseProtocol
from laken.local_lakehouse import LocalLakehouse
from laken.types import DfKind, InputFrame, OutputFrame, WriteMode


def read_table(
    name: str,
    *,
    frame_type: DfKind | None = None,
    max_mirror_mb: int | None = None,
    max_sample_rows: int | None = None,
) -> OutputFrame:
    return Lakehouse().read_table(
        name,
        frame_type=frame_type,
        max_mirror_mb=max_mirror_mb,
        max_sample_rows=max_sample_rows,
    )


def write_table(df: InputFrame, name: str, *, mode: WriteMode = "overwrite") -> None:
    Lakehouse().write_table(df, name, mode=mode)


__all__ = [
    "DfKind",
    "FabricLakehouse",
    "InputFrame",
    "Lakehouse",
    "LakehouseProtocol",
    "LocalLakehouse",
    "OutputFrame",
    "WriteMode",
    "load_environment",
    "read_table",
    "write_table",
]
