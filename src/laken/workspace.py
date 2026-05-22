import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import pyarrow as pa

DEFAULT_MAX_MIRROR_MB = 100
DEFAULT_MAX_SAMPLE_ROWS = 10_000


def mirror_limit_bytes(max_mirror_mb: int) -> int:
    return max_mirror_mb * 1_000_000


@dataclass(frozen=True)
class FabricTableInfo:
    table: str
    delta_version: int
    workspace_id: str | None = None
    lakehouse_id: str | None = None
    size_bytes: int | None = None


class FabricTableFetcher(Protocol):
    def inspect_table(self, name: str) -> FabricTableInfo: ...

    def fetch_table(self, name: str, *, max_rows: int | None = None) -> pa.Table: ...


class TableMetadataStore:
    def __init__(self, path: str | os.PathLike):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> dict:
        if not self._path.is_file():
            return {"tables": {}}
        with self._path.open(encoding="utf-8") as file:
            data = json.load(file)
        if "tables" not in data or not isinstance(data["tables"], dict):
            return {"tables": {}}
        return data

    def save(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, sort_keys=True)
            file.write("\n")
        temp_path.replace(self._path)

    def table(self, name: str) -> dict | None:
        return self.load()["tables"].get(name)

    def upsert(self, name: str, entry: dict) -> None:
        data = self.load()
        data["tables"][name] = entry
        self.save(data)

    def remove(self, name: str) -> None:
        data = self.load()
        data["tables"].pop(name, None)
        self.save(data)

    def tables(self) -> dict:
        return self.load()["tables"]


def utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")
