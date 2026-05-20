import os
import shutil
from pathlib import Path
from typing import Literal, overload

import pandas as pd
import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq
from pyspark.sql import DataFrame as SparkDataFrame

from laken.frames import from_arrow, to_arrow
from laken.paths import format_table_name, parse_table_name
from laken.types import DfKind, InputFrame, WriteMode


class LocalLakehouse:
    def __init__(self, root: str | os.PathLike = "./lakehouse"):
        self._root = Path(root).resolve()
        (self._root / "Files").mkdir(parents=True, exist_ok=True)
        (self._root / "Tables").mkdir(parents=True, exist_ok=True)

    def _table_dir(self, name: str) -> Path:
        schema, table = parse_table_name(name)
        return self._root / "Tables" / schema / table

    def _file_path(self, path: str) -> Path:
        normalized = Path(path)
        if normalized.is_absolute() or ".." in normalized.parts:
            raise ValueError(f"invalid file path: {path}")
        return self._root / "Files" / normalized

    def _next_part_path(self, directory: Path) -> Path:
        existing = sorted(directory.glob("part-*.parquet"))
        if not existing:
            return directory / "part-0000.parquet"
        last = existing[-1].stem.split("-")[-1]
        next_index = int(last) + 1
        return directory / f"part-{next_index:04d}.parquet"

    @overload
    def read_table(self, name: str, *, as_: Literal["spark"] = "spark") -> SparkDataFrame: ...

    @overload
    def read_table(self, name: str, *, as_: Literal["pandas"]) -> pd.DataFrame: ...

    @overload
    def read_table(self, name: str, *, as_: Literal["polars"]) -> pl.DataFrame: ...

    def read_table(
        self, name: str, *, as_: DfKind = "spark"
    ) -> SparkDataFrame | pd.DataFrame | pl.DataFrame:
        table_dir = self._table_dir(name)
        if not table_dir.is_dir():
            raise FileNotFoundError(f"table not found: {name}")
        dataset = pq.ParquetDataset(table_dir)
        return from_arrow(dataset.read(), as_)

    def write_table(
        self, df: InputFrame, name: str, *, mode: WriteMode = "overwrite"
    ) -> None:
        table_dir = self._table_dir(name)
        arrow_table = to_arrow(df)
        if mode == "overwrite":
            shutil.rmtree(table_dir, ignore_errors=True)
            table_dir.mkdir(parents=True, exist_ok=True)
            pq.write_table(arrow_table, table_dir / "part-0000.parquet")
            return
        table_dir.mkdir(parents=True, exist_ok=True)
        pq.write_table(arrow_table, self._next_part_path(table_dir))

    def list_tables(self) -> list[str]:
        tables_root = self._root / "Tables"
        names: list[str] = []
        if not tables_root.is_dir():
            return names
        for schema_dir in sorted(tables_root.iterdir()):
            if not schema_dir.is_dir():
                continue
            for table_dir in sorted(schema_dir.iterdir()):
                if table_dir.is_dir() and any(table_dir.glob("*.parquet")):
                    names.append(format_table_name(schema_dir.name, table_dir.name))
        return names

    def table_exists(self, name: str) -> bool:
        return self._table_dir(name).is_dir()

    def drop_table(self, name: str) -> None:
        shutil.rmtree(self._table_dir(name), ignore_errors=True)

    @overload
    def read_file(self, path: str, *, as_: Literal["spark"] = "spark") -> SparkDataFrame: ...

    @overload
    def read_file(self, path: str, *, as_: Literal["pandas"]) -> pd.DataFrame: ...

    @overload
    def read_file(self, path: str, *, as_: Literal["polars"]) -> pl.DataFrame: ...

    def read_file(
        self, path: str, *, as_: DfKind = "spark"
    ) -> SparkDataFrame | pd.DataFrame | pl.DataFrame:
        file_path = self._file_path(path)
        if not file_path.is_file():
            raise FileNotFoundError(f"file not found: {path}")
        return from_arrow(pq.read_table(file_path), as_)

    def write_file(
        self, df: InputFrame, path: str, *, mode: WriteMode = "overwrite"
    ) -> None:
        file_path = self._file_path(path)
        arrow_table = to_arrow(df)
        if mode == "overwrite":
            file_path.parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(arrow_table, file_path)
            return
        if file_path.is_file():
            existing = pq.read_table(file_path)
            pq.write_table(pa.concat_tables([existing, arrow_table]), file_path)
            return
        file_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(arrow_table, file_path)

    def list_files(self, path: str = "") -> list[str]:
        base = self._file_path(path) if path else self._root / "Files"
        if not base.is_dir():
            return []
        files_root = self._root / "Files"
        results: list[str] = []
        for item in sorted(base.rglob("*")):
            if item.is_file():
                results.append(str(item.relative_to(files_root)).replace("\\", "/"))
        return results

    def file_exists(self, path: str) -> bool:
        return self._file_path(path).exists()

    def delete_file(self, path: str) -> None:
        self._file_path(path).unlink(missing_ok=True)
