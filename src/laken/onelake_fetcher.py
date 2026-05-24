import os
import time

import pyarrow as pa
import requests
from deltalake import DeltaTable

from laken.table_names import (
    TableRef,
    format_fabric_table_name,
    parse_table_ref,
    table_name_parts,
)
from laken.workspace import FabricTableInfo

ONELAKE_SCOPE = "https://storage.azure.com/.default"
FABRIC_API_SCOPE = "https://api.fabric.microsoft.com/.default"
REQUEST_TIMEOUT_SECONDS = 60
TOKEN_CACHE_SECONDS = 3000
_token_cache: dict[str, tuple[str, float]] = {}


class OneLakeFabricFetcher:
    def __init__(
        self,
        *,
        workspace_name: str,
        lakehouse: str,
        workspace_id: str,
        lakehouse_id: str,
    ):
        self._workspace_name = workspace_name
        self._lakehouse = lakehouse
        self._workspace_id = workspace_id
        self._lakehouse_id = lakehouse_id

    def inspect_table(self, name: str) -> FabricTableInfo:
        ref, fabric_name = self._resolve_fetch_target(name)
        delta_table = self._delta_table(ref)
        actions = delta_table.get_add_actions()
        size_bytes = sum(
            value for value in actions.column("size_bytes").to_pylist() if value is not None
        )
        return FabricTableInfo(
            table=fabric_name,
            delta_version=delta_table.version(),
            workspace_id=self._workspace_id,
            lakehouse_id=self._lakehouse_id,
            size_bytes=size_bytes,
        )

    def fetch_table(self, name: str, *, max_rows: int | None = None) -> pa.Table:
        ref, _ = self._resolve_fetch_target(name)
        delta_table = self._delta_table(ref)
        if max_rows is None:
            return delta_table.to_pyarrow_table()
        return delta_table.to_pyarrow_dataset().head(max_rows)

    def _fabric_table_name(self, ref: TableRef) -> str:
        return format_fabric_table_name(
            self._workspace_name,
            self._lakehouse,
            ref.schema,
            ref.table,
        )

    def _resolve_fetch_target(self, name: str) -> tuple[TableRef, str]:
        stripped = name.strip()
        parts = table_name_parts(stripped)
        if len(parts) == 4:
            return TableRef(schema=parts[2], table=parts[3]), stripped
        ref = parse_table_ref(stripped)
        return ref, self._fabric_table_name(ref)

    def _delta_table(self, ref: TableRef) -> DeltaTable:
        return DeltaTable(
            _table_uri(
                ref,
                workspace_id=self._workspace_id,
                lakehouse_id=self._lakehouse_id,
            ),
            storage_options=_storage_options(),
        )


def default_fabric_fetcher(
    *,
    lakehouse: str | None = None,
    lakehouse_id: str | None = None,
    workspace_id: str | None = None,
    workspace_name: str | None = None,
) -> OneLakeFabricFetcher | None:
    if not _azure_credentials_available():
        return None
    resolved_workspace_name = workspace_name or os.getenv("FABRIC_WORKSPACE_NAME")
    resolved_lakehouse = lakehouse or os.getenv("FABRIC_LAKEHOUSE_NAME")
    resolved_workspace_id = workspace_id or os.getenv("FABRIC_WORKSPACE_ID")
    resolved_lakehouse_id = lakehouse_id or os.getenv("FABRIC_LAKEHOUSE_ID")
    if not (
        resolved_workspace_name
        and resolved_lakehouse
        and resolved_workspace_id
        and resolved_lakehouse_id
    ):
        return None
    return OneLakeFabricFetcher(
        workspace_name=resolved_workspace_name,
        lakehouse=resolved_lakehouse,
        workspace_id=resolved_workspace_id,
        lakehouse_id=resolved_lakehouse_id,
    )


def _table_uri(
    ref: TableRef,
    *,
    workspace_id: str,
    lakehouse_id: str,
) -> str:
    table_path = ref.table if ref.schema == "dbo" else f"{ref.schema}/{ref.table}"
    root = f"abfss://{workspace_id}@onelake.dfs.fabric.microsoft.com/{lakehouse_id}/"
    return f"{root}Tables/{table_path}"


def _storage_options() -> dict[str, str]:
    return {
        "bearer_token": _fabric_access_token(),
        "use_fabric_endpoint": "true",
    }


def _fabric_access_token() -> str:
    return _access_token(ONELAKE_SCOPE)


def _access_token(scope: str) -> str:
    now = time.monotonic()
    cached = _token_cache.get(scope)
    if cached is not None and now < cached[1]:
        return cached[0]
    tenant_id = os.environ["AZURE_TENANT_ID"]
    response = requests.post(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        data={
            "client_id": os.environ["AZURE_CLIENT_ID"],
            "client_secret": os.environ["AZURE_CLIENT_SECRET"],
            "grant_type": "client_credentials",
            "scope": scope,
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("OAuth response missing access_token")
    _token_cache[scope] = (token, now + TOKEN_CACHE_SECONDS)
    return token


def _azure_credentials_available() -> bool:
    return all(
        os.getenv(name) for name in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET")
    )
