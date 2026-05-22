from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from deltalake import DeltaTable, write_deltalake

from laken.frames import from_arrow, to_arrow
from laken.onelake_fetcher import default_fabric_fetcher
from laken.table_names import (
    format_fabric_table_name,
    format_table_name,
    is_four_part_table_name,
    parse_table_name,
)
from laken.types import DfKind, InputFrame, OutputFrame, WriteMode
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

logger = logging.getLogger(__name__)


def _format_bytes(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


class LocalLakehouse:
    def __init__(
        self,
        root: str | os.PathLike = ".laken/workspace",
        *,
        lakehouse: str | None = None,
        workspace_id: str | None = None,
        workspace_name: str | None = None,
        metadata_path: str | os.PathLike | None = None,
        fabric_fetcher: FabricTableFetcher | None = None,
        max_mirror_mb: int = DEFAULT_MAX_MIRROR_MB,
        max_sample_rows: int = DEFAULT_MAX_SAMPLE_ROWS,
    ):
        self._root = Path(root).resolve()
        self._lakehouse = lakehouse or os.getenv("FABRIC_LAKEHOUSE_NAME")
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

    def _resolve_fabric_fetcher(self) -> FabricTableFetcher | None:
        if self._fabric_fetcher_resolved:
            return self._fabric_fetcher
        self._fabric_fetcher = default_fabric_fetcher(
            lakehouse=self._lakehouse,
            workspace_id=self._workspace_id,
            workspace_name=self._workspace_name,
        )
        self._fabric_fetcher_resolved = True
        return self._fabric_fetcher

    def _default_metadata_path(self) -> Path:
        if self._root.name == "workspace":
            return self._root.parent / "metadata" / "tables.json"
        return self._root / "metadata" / "tables.json"

    def _table_dir(self, name: str) -> Path:
        schema, table = parse_table_name(name)
        if schema == "dbo":
            return self._root / "Tables" / table
        return self._root / "Tables" / schema / table

    def _table_key(self, name: str) -> str:
        schema, table = parse_table_name(name)
        if schema == "dbo":
            return table
        return format_table_name(schema, table)

    def _file_path(self, path: str) -> Path:
        normalized = Path(path)
        if normalized.is_absolute() or ".." in normalized.parts:
            raise ValueError(f"invalid file path: {path}")
        return self._root / "Files" / normalized

    def _source_from_info(self, info: FabricTableInfo) -> dict:
        return {
            "workspace_id": info.workspace_id,
            "lakehouse_id": info.lakehouse_id,
            "table": info.table,
            "delta_version": info.delta_version,
        }

    def _write_delta_table(self, table_dir: Path, arrow_table: pa.Table) -> None:
        shutil.rmtree(table_dir, ignore_errors=True)
        table_dir.parent.mkdir(parents=True, exist_ok=True)
        write_deltalake(
            str(table_dir),
            arrow_table,
            mode="overwrite",
            schema_mode="overwrite",
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

    def _cached_max_sample_rows(self, entry: dict) -> int:
        cache = entry.get("cache", {})
        if "max_sample_rows" in cache:
            return int(cache["max_sample_rows"])
        if "sample_rows" in cache:
            return int(cache["sample_rows"])
        return self._max_sample_rows

    def _fetch_and_cache(
        self,
        local_name: str,
        fetch_name: str,
        *,
        max_mirror_mb: int,
        max_sample_rows: int,
    ) -> dict:
        fabric_fetcher = self._resolve_fabric_fetcher()
        if fabric_fetcher is None:
            raise FileNotFoundError(f"table not found: {local_name}")
        try:
            info = fabric_fetcher.inspect_table(fetch_name)
        except Exception as err:
            if type(err).__name__ != "TableNotFoundError":
                raise
            raise FileNotFoundError(f"table not found: {local_name}") from err
        table_dir = self._table_dir(local_name)
        key = self._table_key(local_name)
        remote_size_bytes = info.size_bytes or 0
        mirror_limit = mirror_limit_bytes(max_mirror_mb)
        if remote_size_bytes > mirror_limit:
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
        return bool(self._workspace_name and self._lakehouse)

    def _resolve_fetch_name(self, name: str) -> str:
        stripped = name.strip()
        if is_four_part_table_name(stripped):
            return stripped
        if self._can_resolve_fabric_name():
            schema, table = parse_table_name(stripped)
            return format_fabric_table_name(self._workspace_name, self._lakehouse, schema, table)
        return stripped

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
        self._fetch_and_cache(
            name,
            self._resolve_fetch_name(name),
            max_mirror_mb=cache_mb,
            max_sample_rows=cache_rows,
        )

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
            return
        source = entry.get("source", {})
        try:
            current = fabric_fetcher.inspect_table(source.get("table", name))
        except Exception:
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
        refreshed = self._fetch_and_cache(
            name,
            source.get("table", name),
            max_mirror_mb=self._max_mirror_mb,
            max_sample_rows=self._max_sample_rows,
        )
        version = refreshed.get("source", {}).get("delta_version")
        logger.info("Refreshed %s from Fabric version %s.", key, version)

    def reset_table(self, name: str) -> None:
        key = self._table_key(name)
        entry = self._metadata.table(key)
        if entry is None or entry.get("source") is None:
            raise ValueError(f"laken: {key} has no Fabric source to reset.")
        source = entry["source"]
        reset = self._fetch_and_cache(
            name,
            source.get("table", name),
            max_mirror_mb=self._max_mirror_mb,
            max_sample_rows=self._max_sample_rows,
        )
        version = reset.get("source", {}).get("delta_version")
        logger.info("Reset %s to Fabric version %s.", key, version)

    def status(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for key, entry in sorted(self._metadata.tables().items()):
            state = str(entry.get("state", "local"))
            source = entry.get("source", {})
            version = source.get("delta_version")
            notes = self._status_notes(key, entry)
            rows.append(
                {
                    "table": key,
                    "state": state,
                    "source_version": str(version) if version is not None else "-",
                    "notes": notes,
                }
            )
        return rows

    def _status_notes(self, key: str, entry: dict) -> str:
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
            except Exception:
                notes.append("freshness unknown")
            else:
                if current.delta_version != cached_version:
                    notes.append(f"stale: Fabric is {current.delta_version}")
        return ", ".join(notes)

    def read_table(
        self,
        name: str,
        *,
        frame_type: DfKind = "pandas",
        max_mirror_mb: int | None = None,
        max_sample_rows: int | None = None,
    ) -> OutputFrame:
        table_dir = self._table_dir(name)
        if not (table_dir / "_delta_log").is_dir():
            self._hydrate_table(
                name,
                max_mirror_mb=max_mirror_mb,
                max_sample_rows=max_sample_rows,
            )
        self._warn_about_cached_table(name)
        return from_arrow(DeltaTable(str(table_dir)).to_pyarrow_table(), frame_type)

    def load_table_from_warehouse(
        self,
        table_name: str,
        warehouse_name: str,
        *,
        schema: str | None = "dbo",
        workspace_id: str | None = None,
        frame_type: DfKind = "pandas",
    ) -> OutputFrame:
        _ = warehouse_name, schema, workspace_id
        return self.read_file(table_name, frame_type=frame_type)

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
            shutil.rmtree(table_dir, ignore_errors=True)
            table_dir.parent.mkdir(parents=True, exist_ok=True)
            write_deltalake(
                str(table_dir),
                arrow_table,
                mode="overwrite",
                schema_mode="overwrite",
            )
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

    def read_file(self, path: str, *, frame_type: DfKind = "pandas") -> OutputFrame:
        file_path = self._file_path(path)
        if not file_path.is_file():
            raise FileNotFoundError(f"file not found: {path}")
        return from_arrow(pq.read_table(file_path), frame_type)

    def write_file(self, df: InputFrame, path: str, *, mode: WriteMode = "overwrite") -> None:
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
