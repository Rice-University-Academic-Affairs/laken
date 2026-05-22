from __future__ import annotations

import os
import shutil
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.dataset as pads
import pyarrow.parquet as pq
import requests
from deltalake import DeltaTable, write_deltalake
from deltalake.exceptions import TableNotFoundError

from laken._env import load_environment
from laken.frames import from_arrow, to_arrow
from laken.logger import ensure_logging, logger
from laken.onelake_fetcher import default_fabric_fetcher
from laken.table_names import (
    TableRef,
    format_table_name,
    is_four_part_table_name,
    resolve_table_ref,
)
from laken.types import DataFrameTypeName, FileWrite, InputFrame, OutputFrame, WriteMode
from laken.workspace import (
    DEFAULT_MAX_MIRROR_MB,
    DEFAULT_MAX_SAMPLE_ROWS,
    FabricTableFetcher,
    FabricTableInfo,
    TableMetadataStore,
    display_path,
    mirror_limit_bytes,
    utc_timestamp,
)


class LocalLakehouse:
    def __init__(
        self,
        root: str | os.PathLike = ".laken/workspace",
        *,
        lakehouse: str | None = None,
        lakehouse_id: str | None = None,
        workspace_id: str | None = None,
        workspace_name: str | None = None,
        metadata_path: str | os.PathLike | None = None,
        fabric_fetcher: FabricTableFetcher | None = None,
        max_mirror_mb: int = DEFAULT_MAX_MIRROR_MB,
        max_sample_rows: int = DEFAULT_MAX_SAMPLE_ROWS,
    ):
        load_environment()
        ensure_logging()
        self._root = Path(root).resolve()
        self._lakehouse = lakehouse or os.getenv("FABRIC_LAKEHOUSE_NAME")
        self._lakehouse_id = lakehouse_id or os.getenv("FABRIC_LAKEHOUSE_ID")
        self._workspace_id = workspace_id or os.getenv("FABRIC_WORKSPACE_ID")
        self._workspace_name = workspace_name or os.getenv("FABRIC_WORKSPACE_NAME")
        self._fabric_fetcher_arg = fabric_fetcher
        self._fabric_fetcher_resolved = fabric_fetcher is not None
        self._fabric_fetcher = fabric_fetcher
        self._max_mirror_mb = max_mirror_mb
        self._max_sample_rows = max_sample_rows
        self._metadata = TableMetadataStore(
            metadata_path if metadata_path is not None else self._default_metadata_path()
        )
        (self._root / "Files").mkdir(parents=True, exist_ok=True)
        (self._root / "Tables").mkdir(parents=True, exist_ok=True)
        logger.debug(
            "LocalLakehouse ready at %s (lakehouse=%s, workspace=%s)",
            self._root,
            self._lakehouse,
            self._workspace_name,
        )

    def read_table(
        self,
        name: str,
        *,
        frame_type: DataFrameTypeName = "pandas",
        max_mirror_mb: int | None = None,
        max_sample_rows: int | None = None,
    ) -> OutputFrame:
        table_dir = self._table_dir(name)
        if not (table_dir / "_delta_log").is_dir():
            logger.debug("No local Delta cache for %s", name)
            self._hydrate_table(
                name,
                max_mirror_mb=max_mirror_mb,
                max_sample_rows=max_sample_rows,
            )
        else:
            key = self._table_key(name)
            entry = self._metadata.table(key)
            state = entry.get("state", "local") if entry is not None else "local"
            logger.debug("Reading %s from local Delta cache (state=%s)", name, state)
        self._warn_about_cached_table(name)
        return from_arrow(DeltaTable(str(table_dir)).to_pyarrow_table(), frame_type)

    def load_table_from_warehouse(
        self,
        table_name: str,
        warehouse_name: str,
        *,
        schema: str | None = "dbo",
        workspace_id: str | None = None,
        frame_type: DataFrameTypeName = "pandas",
    ) -> OutputFrame:
        _ = table_name, warehouse_name, schema, workspace_id, frame_type
        raise NotImplementedError("load_table_from_warehouse is only available in Fabric notebooks")

    def write_table(self, df: InputFrame, name: str, *, mode: WriteMode = "overwrite") -> None:
        table_dir = self._table_dir(name)
        arrow_table = to_arrow(df)
        key = self._table_key(name)
        existing = self._metadata.table(key)
        source = existing.get("source") if existing is not None else None
        created_at = existing.get("created_at") if existing is not None else None
        if existing is not None and existing.get("state") in {"mirror", "sample"}:
            logger.info("%s was a Fabric-backed mirror.", key)
            logger.info(
                "This write converts it to a local table. "
                "It will not be refreshed from Fabric unless reset."
            )
        if mode == "overwrite" or not (table_dir / "_delta_log").is_dir():
            self._write_delta_table(table_dir, arrow_table)
        else:
            table_dir.parent.mkdir(parents=True, exist_ok=True)
            write_deltalake(str(table_dir), arrow_table, mode="append")
        entry = {
            "state": "local",
            "path": display_path(table_dir),
            "created_at": created_at or utc_timestamp(),
        }
        if source is not None:
            entry["source"] = source
        self._metadata.upsert(key, entry)

    def list_tables(self) -> list[str]:
        tables_root = self._root / "Tables"
        names: list[str] = []
        if not tables_root.is_dir():
            return names
        for item in sorted(tables_root.iterdir()):
            if not item.is_dir():
                continue
            if (item / "_delta_log").is_dir():
                names.append(format_table_name("dbo", item.name))
                continue
            for table_dir in sorted(item.iterdir()):
                if table_dir.is_dir() and (table_dir / "_delta_log").is_dir():
                    names.append(format_table_name(item.name, table_dir.name))
        return sorted(names)

    def table_exists(self, name: str) -> bool:
        return (self._table_dir(name) / "_delta_log").is_dir()

    def drop_table(self, name: str) -> None:
        shutil.rmtree(self._table_dir(name), ignore_errors=True)
        self._metadata.remove(self._table_key(name))

    def read_file(self, path: str) -> bytes:
        file_path = self._file_path(path)
        if file_path.is_file() or _parquet_dataset_dir(file_path).is_dir():
            logger.debug("Reading local file %s", path)
            return _read_stored_file_bytes(file_path)
        fabric_fetcher = self._resolve_fabric_fetcher()
        if fabric_fetcher is None:
            raise FileNotFoundError(f"file not found: {path}")
        logger.debug("Hydrating file %s from Fabric", path)
        data = fabric_fetcher.fetch_file(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(data)
        return data

    def write_file(self, data: FileWrite, path: str, *, mode: WriteMode = "overwrite") -> None:
        file_path = self._file_path(path)
        if isinstance(data, bytes):
            _ensure_storage_compatible(
                file_path,
                expected="file",
                mode=mode,
                suffix=file_path.suffix.lower(),
            )
            _write_bytes(file_path, data, mode=mode)
            return
        suffix = file_path.suffix.lower()
        arrow_table = to_arrow(data)
        if suffix == ".parquet":
            expected = "parquet_dataset" if mode == "append" else "file"
            _ensure_storage_compatible(
                file_path,
                expected=expected,
                mode=mode,
                suffix=suffix,
            )
            if mode == "overwrite":
                _write_parquet_overwrite(file_path, arrow_table)
            else:
                _write_parquet_append(file_path, arrow_table)
            return
        if suffix == ".csv":
            _ensure_storage_compatible(
                file_path,
                expected="file",
                mode=mode,
                suffix=suffix,
            )
            _write_csv(file_path, arrow_table, mode=mode)
            return
        raise ValueError(f"unsupported file extension for dataframe write: {suffix}")

    def file_exists(self, path: str) -> bool:
        file_path = self._file_path(path)
        return file_path.is_file() or _parquet_dataset_dir(file_path).is_dir()

    def delete_file(self, path: str) -> None:
        file_path = self._file_path(path)
        file_path.unlink(missing_ok=True)
        shutil.rmtree(_parquet_dataset_dir(file_path), ignore_errors=True)

    def refresh_table(self, name: str) -> None:
        key = self._table_key(name)
        entry = self._metadata.table(key)
        if entry is None:
            raise FileNotFoundError(f"table not found: {name}")
        if entry.get("state") == "local":
            logger.info("%s is local-only and has no Fabric source to refresh.", key)
            return
        source = entry.get("source")
        if source is None:
            raise ValueError(f"table has no Fabric source: {key}")
        cache_mb, cache_rows, force_sample = self._stored_cache_policy(entry)
        refreshed = self._fetch_and_cache(
            name,
            source.get("table", name),
            max_mirror_mb=cache_mb,
            max_sample_rows=cache_rows,
            force_sample=force_sample,
        )
        version = refreshed.get("source", {}).get("delta_version")
        logger.info("Refreshed %s from Fabric version %s.", key, version)

    def reset_table(self, name: str) -> None:
        key = self._table_key(name)
        entry = self._metadata.table(key)
        if entry is None or entry.get("source") is None:
            raise ValueError(f"laken: {key} has no Fabric source to reset.")
        source = entry["source"]
        cache_mb, cache_rows, force_sample = self._stored_cache_policy(entry)
        reset = self._fetch_and_cache(
            name,
            source.get("table", name),
            max_mirror_mb=cache_mb,
            max_sample_rows=cache_rows,
            force_sample=force_sample,
        )
        version = reset.get("source", {}).get("delta_version")
        logger.info("Reset %s to Fabric version %s.", key, version)

    def status(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        seen: set[str] = set()
        for key, entry in sorted(self._metadata.tables().items()):
            seen.add(key)
            rows.append(self._status_row(key, entry))
        for key in self._metadata_keys_on_disk():
            if key in seen:
                continue
            rows.append(self._status_row(key, self._inferred_metadata_entry(key)))
        return sorted(rows, key=lambda row: row["table"])

    def _table_ref(self, name: str) -> TableRef:
        return resolve_table_ref(
            name,
            workspace_name=self._workspace_name,
            workspace_id=self._workspace_id,
            lakehouse_name=self._lakehouse,
            lakehouse_id=self._lakehouse_id,
        )

    def _table_dir(self, name: str) -> Path:
        ref = self._table_ref(name)
        if ref.schema == "dbo":
            return self._root / "Tables" / ref.table
        return self._root / "Tables" / ref.schema / ref.table

    def _hydrate_table(
        self,
        name: str,
        *,
        max_mirror_mb: int | None = None,
        max_sample_rows: int | None = None,
    ) -> None:
        cache_mb, cache_rows = self._resolve_cache_limits(
            max_mirror_mb=max_mirror_mb,
            max_sample_rows=max_sample_rows,
        )
        fetch_name = self._resolve_fetch_name(name)
        logger.debug("Hydrating %s from Fabric (%s)", name, fetch_name)
        self._fetch_and_cache(
            name,
            fetch_name,
            max_mirror_mb=cache_mb,
            max_sample_rows=cache_rows,
        )

    def _table_key(self, name: str) -> str:
        return self._table_ref(name).metadata_key()

    def _warn_about_cached_table(self, name: str) -> None:
        key = self._table_key(name)
        entry = self._metadata.table(key)
        if entry is None or entry.get("state") not in {"mirror", "sample"}:
            return
        if entry.get("state") == "sample":
            sample_rows = self._cached_max_sample_rows(entry)
            logger.info("%s is using a %s-row development sample.", key, f"{sample_rows:,}")
        fabric_fetcher = self._resolve_fabric_fetcher()
        if fabric_fetcher is None:
            logger.info(
                "%s is cached Fabric data (%s). Credentials are not configured; "
                "using local cache without checking freshness.",
                key,
                entry.get("state"),
            )
            return
        source = entry.get("source", {})
        try:
            current = fabric_fetcher.inspect_table(source.get("table", name))
        except _FRESHNESS_CHECK_ERRORS:
            logger.info("Could not check Fabric freshness. Using local cached %s.", key)
            return
        cached_version = source.get("delta_version")
        if cached_version is not None and current.delta_version != cached_version:
            logger.info("%s is cached from Fabric version %s.", key, cached_version)
            logger.info("Fabric is now at version %s.", current.delta_version)
            logger.info(
                "Using the local cached version. Run `laken refresh %s` to update.",
                key,
            )

    def _resolve_cache_limits(
        self,
        *,
        max_mirror_mb: int | None,
        max_sample_rows: int | None,
    ) -> tuple[int, int]:
        resolved_mb = max_mirror_mb if max_mirror_mb is not None else self._max_mirror_mb
        resolved_rows = max_sample_rows if max_sample_rows is not None else self._max_sample_rows
        return resolved_mb, resolved_rows

    def _resolve_fetch_name(self, name: str) -> str:
        stripped = name.strip()
        if is_four_part_table_name(stripped):
            return stripped
        ref = self._table_ref(stripped)
        if self._can_resolve_fabric_name():
            return TableRef(
                schema=ref.schema,
                table=ref.table,
                workspace=ref.workspace or self._workspace_name,
                lakehouse=ref.lakehouse or self._lakehouse,
            ).fabric_four_part()
        return stripped

    def _fetch_and_cache(
        self,
        local_name: str,
        fetch_name: str,
        *,
        max_mirror_mb: int,
        max_sample_rows: int,
        force_sample: bool = False,
    ) -> dict:
        fabric_fetcher = self._resolve_fabric_fetcher()
        if fabric_fetcher is None:
            raise FileNotFoundError(f"table not found: {local_name}")
        try:
            info = fabric_fetcher.inspect_table(fetch_name)
        except TableNotFoundError as err:
            raise FileNotFoundError(f"table not found: {local_name}") from err
        table_dir = self._table_dir(local_name)
        key = self._table_key(local_name)
        remote_size_bytes = info.size_bytes or 0
        mirror_limit = mirror_limit_bytes(max_mirror_mb)
        if force_sample or remote_size_bytes > mirror_limit:
            logger.info(
                "%s is %s on Fabric (over %s MB limit).",
                key,
                _format_bytes(remote_size_bytes),
                max_mirror_mb,
            )
            logger.info("Caching a %s-row development sample instead.", f"{max_sample_rows:,}")
            arrow_table = fabric_fetcher.fetch_table(fetch_name, max_rows=max_sample_rows)
            self._write_delta_table(table_dir, arrow_table)
            entry = {
                "state": "sample",
                "path": display_path(table_dir),
                "source": self._source_from_info(info),
                "cache": {
                    "mode": "sample",
                    "remote_size_bytes": remote_size_bytes,
                    "max_sample_rows": max_sample_rows,
                    "fetched_at": utc_timestamp(),
                },
            }
            self._metadata.upsert(key, entry)
            return entry
        logger.info("Fetching %s from Fabric...", key)
        arrow_table = fabric_fetcher.fetch_table(fetch_name, max_rows=None)
        self._write_delta_table(table_dir, arrow_table)
        entry = {
            "state": "mirror",
            "path": display_path(table_dir),
            "source": self._source_from_info(info),
            "cache": {
                "mode": "full",
                "fetched_at": utc_timestamp(),
                "remote_size_bytes": remote_size_bytes,
            },
        }
        self._metadata.upsert(key, entry)
        logger.info("Cached %s locally as a Delta table.", key)
        return entry

    def _can_resolve_fabric_name(self) -> bool:
        return bool(
            self._workspace_name and self._workspace_id and self._lakehouse and self._lakehouse_id
        )

    def _resolve_fabric_fetcher(self) -> FabricTableFetcher | None:
        if self._fabric_fetcher_resolved:
            return self._fabric_fetcher
        logger.debug("Resolving Fabric fetcher from environment")
        self._fabric_fetcher = default_fabric_fetcher(
            lakehouse=self._lakehouse,
            lakehouse_id=self._lakehouse_id,
            workspace_id=self._workspace_id,
            workspace_name=self._workspace_name,
        )
        self._fabric_fetcher_resolved = True
        return self._fabric_fetcher

    def _write_delta_table(self, table_dir: Path, arrow_table: pa.Table) -> None:
        parent = table_dir.parent
        parent.mkdir(parents=True, exist_ok=True)
        staging = parent / f".{table_dir.name}.staging"
        backup = parent / f".{table_dir.name}.backup"
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(backup, ignore_errors=True)
        try:
            write_deltalake(
                str(staging),
                arrow_table,
                mode="overwrite",
                schema_mode="overwrite",
            )
            if table_dir.exists():
                table_dir.rename(backup)
            staging.rename(table_dir)
            shutil.rmtree(backup, ignore_errors=True)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            if backup.exists() and not table_dir.exists():
                backup.rename(table_dir)
            raise

    def _stored_cache_policy(self, entry: dict) -> tuple[int, int, bool]:
        cache = entry.get("cache", {})
        state = entry.get("state")
        if state == "sample" or cache.get("mode") == "sample":
            sample_rows = self._cached_max_sample_rows(entry)
            mirror_mb = cache.get("max_mirror_mb")
            resolved_mb = int(mirror_mb) if mirror_mb is not None else self._max_mirror_mb
            return resolved_mb, sample_rows, True
        mirror_mb = cache.get("max_mirror_mb")
        sample_rows = cache.get("max_sample_rows")
        resolved_mb = int(mirror_mb) if mirror_mb is not None else self._max_mirror_mb
        resolved_rows = int(sample_rows) if sample_rows is not None else self._max_sample_rows
        return resolved_mb, resolved_rows, False

    def _source_from_info(self, info: FabricTableInfo) -> dict:
        return {
            "workspace_id": info.workspace_id,
            "lakehouse_id": info.lakehouse_id,
            "table": info.table,
            "delta_version": info.delta_version,
        }

    def _cached_max_sample_rows(self, entry: dict) -> int:
        cache = entry.get("cache", {})
        if "max_sample_rows" in cache:
            return int(cache["max_sample_rows"])
        if "sample_rows" in cache:
            return int(cache["sample_rows"])
        return self._max_sample_rows

    def _status_row(self, key: str, entry: dict) -> dict[str, str]:
        state = str(entry.get("state", "local"))
        source = entry.get("source", {})
        version = source.get("delta_version")
        notes = self._status_notes(key, entry)
        return {
            "table": key,
            "state": state,
            "source_version": str(version) if version is not None else "-",
            "notes": notes,
        }

    def _metadata_keys_on_disk(self) -> list[str]:
        keys: list[str] = []
        for name in self.list_tables():
            keys.append(self._table_key(name))
        return keys

    def _inferred_metadata_entry(self, key: str) -> dict:
        return {
            "state": "local",
            "path": display_path(self._table_dir_from_key(key)),
            "inferred": True,
        }

    def _table_dir_from_key(self, key: str) -> Path:
        if "." in key:
            schema, table = key.split(".", 1)
        else:
            schema, table = "dbo", key
        if schema == "dbo":
            return self._root / "Tables" / table
        return self._root / "Tables" / schema / table

    def _status_notes(self, key: str, entry: dict) -> str:
        if entry.get("inferred"):
            return "no metadata record"
        state = entry.get("state")
        if state == "local":
            return "local-only"
        notes = []
        if state == "sample":
            sample_rows = self._cached_max_sample_rows(entry)
            notes.append(f"{sample_rows:,}-row sample")
        source = entry.get("source", {})
        cached_version = source.get("delta_version")
        fabric_fetcher = self._resolve_fabric_fetcher()
        if fabric_fetcher is not None and cached_version is not None:
            try:
                current = fabric_fetcher.inspect_table(source.get("table", key))
            except _FRESHNESS_CHECK_ERRORS:
                notes.append("freshness unknown")
            else:
                if current.delta_version != cached_version:
                    notes.append(f"stale: Fabric is {current.delta_version}")
        return ", ".join(notes)

    def _default_metadata_path(self) -> Path:
        if self._root.name == "workspace":
            return self._root.parent / "metadata" / "tables.json"
        return self._root / "metadata" / "tables.json"

    def _file_path(self, path: str) -> Path:
        normalized = Path(path)
        if normalized.is_absolute() or ".." in normalized.parts:
            raise ValueError(f"invalid file path: {path}")
        return self._root / "Files" / normalized


_FRESHNESS_CHECK_ERRORS = (TableNotFoundError, requests.RequestException, OSError)


def _parquet_dataset_dir(file_path: Path) -> Path:
    return file_path.parent / f"{file_path.name}.d"


def _read_stored_file_bytes(file_path: Path) -> bytes:
    dataset_dir = _parquet_dataset_dir(file_path)
    if dataset_dir.is_dir():
        parts = sorted(dataset_dir.glob("part-*.parquet"))
        if len(parts) == 1:
            return parts[0].read_bytes()
        dataset = pads.dataset(dataset_dir, format="parquet")
        sink = pa.BufferOutputStream()
        writer = pq.ParquetWriter(sink, dataset.schema)
        for batch in dataset.to_batches():
            writer.write_batch(batch)
        writer.close()
        return sink.getvalue().to_pybytes()
    return file_path.read_bytes()


def _file_storage_shape(file_path: Path) -> str | None:
    if _parquet_dataset_dir(file_path).is_dir():
        return "parquet_dataset"
    if file_path.is_file():
        return "file"
    return None


def _storage_shapes_compatible(existing: str, expected: str, *, suffix: str) -> bool:
    if existing == expected:
        return True
    return suffix == ".parquet" and existing == "file" and expected == "parquet_dataset"


def _ensure_storage_compatible(
    file_path: Path,
    *,
    expected: str,
    mode: WriteMode,
    suffix: str,
) -> None:
    existing = _file_storage_shape(file_path)
    if existing is None or mode == "overwrite":
        return
    if not _storage_shapes_compatible(existing, expected, suffix=suffix):
        raise ValueError(
            f"cannot {mode} {file_path.name}: existing storage is {existing}, expected {expected}"
        )


def _write_bytes(file_path: Path, data: bytes, *, mode: WriteMode) -> None:
    if mode == "overwrite":
        shutil.rmtree(_parquet_dataset_dir(file_path), ignore_errors=True)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if mode == "append" and file_path.is_file():
        with file_path.open("ab") as handle:
            handle.write(data)
        return
    file_path.write_bytes(data)


def _write_csv(file_path: Path, arrow_table: pa.Table, *, mode: WriteMode) -> None:
    if mode == "overwrite":
        shutil.rmtree(_parquet_dataset_dir(file_path), ignore_errors=True)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if mode == "append" and file_path.is_file():
        existing = pacsv.read_csv(file_path)
        arrow_table = pa.concat_tables([existing, arrow_table])
    pacsv.write_csv(arrow_table, file_path)


def _write_parquet_overwrite(file_path: Path, arrow_table: pa.Table) -> None:
    shutil.rmtree(_parquet_dataset_dir(file_path), ignore_errors=True)
    if file_path.is_file():
        file_path.unlink()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(arrow_table, file_path)


def _write_parquet_append(file_path: Path, arrow_table: pa.Table) -> None:
    dataset_dir = _parquet_dataset_dir(file_path)
    if file_path.is_file():
        dataset_dir.mkdir(parents=True, exist_ok=True)
        file_path.rename(dataset_dir / "part-00000.parquet")
    elif not dataset_dir.is_dir():
        file_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(arrow_table, file_path)
        return
    dataset_dir.mkdir(parents=True, exist_ok=True)
    part_count = len(list(dataset_dir.glob("part-*.parquet")))
    pq.write_table(arrow_table, dataset_dir / f"part-{part_count:05d}.parquet")


def _format_bytes(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"
