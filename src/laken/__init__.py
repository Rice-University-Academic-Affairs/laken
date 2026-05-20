from laken.fabric import FabricLakehouse
from laken.lakehouse import Lakehouse
from laken.local import LocalLakehouse
from laken.protocol import LakehouseProtocol
from laken.types import DfKind, InputFrame, OutputFrame, WriteMode


def read_table(name: str, *, as_: DfKind = "spark") -> OutputFrame:
    return Lakehouse().read_table(name, as_=as_)


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
