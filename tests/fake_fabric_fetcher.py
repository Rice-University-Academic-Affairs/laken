import pyarrow as pa

from laken.workspace import FabricTableInfo


class FakeFabricFetcher:
    def __init__(self, *, inspect_errors: dict[str, Exception] | None = None):
        self.tables: dict[str, dict] = {}
        self.limits: list[int | None] = []
        self.inspect_errors = inspect_errors or {}

    def add(
        self,
        name: str,
        table: pa.Table,
        *,
        version: int,
        size_bytes: int,
        workspace_id: str = "abc",
        lakehouse_id: str = "def",
    ) -> None:
        self.tables[name] = {
            "table": table,
            "info": FabricTableInfo(
                table=name,
                delta_version=version,
                workspace_id=workspace_id,
                lakehouse_id=lakehouse_id,
                row_count=table.num_rows,
                size_bytes=size_bytes,
            ),
        }

    def inspect_table(self, name: str) -> FabricTableInfo:
        if name in self.inspect_errors:
            raise self.inspect_errors[name]
        return self.tables[name]["info"]

    def fetch_table(self, name: str, *, limit: int | None = None) -> pa.Table:
        self.limits.append(limit)
        table = self.tables[name]["table"]
        if limit is None:
            return table
        return table.slice(0, limit)
