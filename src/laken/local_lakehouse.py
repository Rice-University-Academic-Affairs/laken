from __future__ import annotations

import os
import shutil
from pathlib import Path

import pyarrow as pa
from deltalake import DeltaTable, write_deltalake
from deltalake.exceptions import TableNotFoundError

from laken._env import load_environment
from laken.frames import from_arrow, to_arrow
from laken.logger import ensure_logging, logger
from laken.onelake_fetcher import default_fabric_fetcher
from laken.table_names import (
    TableRef,
    format_fabric_table_name,
    format_table_name,
    parse_table_ref,
)
from laken.types import DataFrameTypeName, InputFrame, OutputFrame, WriteMode
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
        self._log_sample_notice(name)
        return from_arrow(DeltaTable(str(table_dir)).to_pyarrow_table(), frame_type)

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

    def _table_ref(self, name: str) -> TableRef:
        return parse_table_ref(name)

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

    def _log_sample_notice(self, name: str) -> None:
        key = self._table_key(name)
        entry = self._metadata.table(key)
        if entry is None or entry.get("state") != "sample":
            return
        sample_rows = self._cached_max_sample_rows(entry)
        logger.info("%s is using a %s-row development sample.", key, f"{sample_rows:,}")

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
        ref = self._table_ref(name)
        if self._can_resolve_fabric_name():
            return format_fabric_table_name(
                self._workspace_name,
                self._lakehouse,
                ref.schema,
                ref.table,
            )
        return name.strip()

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

    def _default_metadata_path(self) -> Path:
        if self._root.name == "workspace":
            return self._root.parent / "metadata" / "tables.json"
        return self._root / "metadata" / "tables.json"


def _format_bytes(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"
