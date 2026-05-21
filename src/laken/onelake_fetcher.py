import os

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
import requests
from deltalake import DeltaTable
from deltalake.fs import DeltaStorageHandler

from laken.paths import format_fabric_table_name, is_four_part_table_name, parse_table_name
from laken.workspace import FabricTableInfo

FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
REQUEST_TIMEOUT_SECONDS = 60


def _azure_credentials_available() -> bool:
    return all(
        os.getenv(name) for name in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET")
    )


def _fabric_access_token() -> str:
    tenant_id = os.environ["AZURE_TENANT_ID"]
    response = requests.post(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        data={
            "client_id": os.environ["AZURE_CLIENT_ID"],
            "client_secret": os.environ["AZURE_CLIENT_SECRET"],
            "grant_type": "client_credentials",
            "scope": FABRIC_SCOPE,
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("OAuth response missing access_token")
    return token


def _storage_options() -> dict[str, str]:
    return {
        "bearer_token": _fabric_access_token(),
        "use_fabric_endpoint": "true",
    }


def _resolve_fabric_table_name(
    name: str,
    *,
    workspace_name: str,
    lakehouse: str,
) -> tuple[str, str, str, str]:
    stripped = name.strip()
    if is_four_part_table_name(stripped):
        parts = stripped.split(".")
        return parts[0], parts[1], parts[2], parts[3]
    schema, table = parse_table_name(stripped)
    return workspace_name, lakehouse, schema, table


def _lakehouse_root_uri(workspace_name: str, lakehouse: str) -> str:
    return f"abfss://{workspace_name}@onelake.dfs.fabric.microsoft.com/{lakehouse}.Lakehouse/"


def _table_uri(workspace_name: str, lakehouse: str, schema: str, table: str) -> str:
    table_path = table if schema == "dbo" else f"{schema}/{table}"
    return f"{_lakehouse_root_uri(workspace_name, lakehouse)}Tables/{table_path}"


def _file_storage_path(path: str) -> str:
    normalized = path.replace("\\", "/").lstrip("/")
    return f"Files/{normalized}"


class OneLakeFabricFetcher:
    def __init__(
        self,
        *,
        workspace_name: str,
        lakehouse: str,
        workspace_id: str | None = None,
        lakehouse_id: str | None = None,
    ):
        self._workspace_name = workspace_name
        self._lakehouse = lakehouse
        self._workspace_id = workspace_id
        self._lakehouse_id = lakehouse_id

    def _delta_table(self, name: str) -> DeltaTable:
        workspace_name, lakehouse, schema, table = _resolve_fabric_table_name(
            name,
            workspace_name=self._workspace_name,
            lakehouse=self._lakehouse,
        )
        return DeltaTable(
            _table_uri(workspace_name, lakehouse, schema, table),
            storage_options=_storage_options(),
        )

    def inspect_table(self, name: str) -> FabricTableInfo:
        delta_table = self._delta_table(name)
        workspace_name, lakehouse, schema, table = _resolve_fabric_table_name(
            name,
            workspace_name=self._workspace_name,
            lakehouse=self._lakehouse,
        )
        fabric_name = format_fabric_table_name(workspace_name, lakehouse, schema, table)
        metadata = delta_table.metadata()
        num_rows = metadata.num_rows if metadata is not None else None
        return FabricTableInfo(
            table=fabric_name,
            delta_version=delta_table.version(),
            workspace_id=self._workspace_id,
            lakehouse_id=self._lakehouse_id,
            row_count=num_rows,
            size_bytes=None,
        )

    def fetch_table(self, name: str, *, limit: int | None = None) -> pa.Table:
        table = self._delta_table(name).to_pyarrow_table()
        if limit is not None:
            return table.slice(0, limit)
        return table

    def fetch_file(self, path: str) -> pa.Table:
        normalized = path.replace("\\", "/").lstrip("/")
        root_uri = _lakehouse_root_uri(self._workspace_name, self._lakehouse)
        storage_path = _file_storage_path(normalized)
        handler = DeltaStorageHandler(root_uri, _storage_options())
        with handler.open_input_file(storage_path) as handle:
            data = handle.read()
        if normalized.endswith(".csv"):
            return pacsv.read_csv(pa.BufferReader(data))
        if normalized.endswith(".parquet"):
            return pq.read_table(pa.BufferReader(data))
        raise ValueError(f"unsupported file type: {path}")


def default_fabric_fetcher(
    *,
    lakehouse: str | None = None,
    workspace_id: str | None = None,
    workspace_name: str | None = None,
) -> OneLakeFabricFetcher | None:
    if not _azure_credentials_available():
        return None
    resolved_workspace_name = workspace_name or os.getenv("FABRIC_WORKSPACE_NAME")
    resolved_lakehouse = lakehouse or os.getenv("FABRIC_LAKEHOUSE_NAME")
    if not resolved_workspace_name or not resolved_lakehouse:
        return None
    return OneLakeFabricFetcher(
        workspace_name=resolved_workspace_name,
        lakehouse=resolved_lakehouse,
        workspace_id=workspace_id or os.getenv("FABRIC_WORKSPACE_ID"),
    )
