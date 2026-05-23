import pyarrow as pa

from laken.workspace import FabricTableInfo


class FakeFabricFetcher:
    def __init__(self, *, inspect_errors: dict[str, Exception] | None = None):
        self.tables: dict[str, dict] = {}
        self.max_rows: list[int | None] = []
        self.inspect_names: list[str] = []
        self.fetch_names: list[str] = []
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
                size_bytes=size_bytes,
            ),
        }

    def inspect_table(self, name: str) -> FabricTableInfo:
        self.inspect_names.append(name)
        if name in self.inspect_errors:
            raise self.inspect_errors[name]
        return self.tables[name]["info"]

    def fetch_table(self, name: str, *, max_rows: int | None = None) -> pa.Table:
        self.fetch_names.append(name)
        self.max_rows.append(max_rows)
        table = self.tables[name]["table"]
        if max_rows is None:
            return table
        return table.slice(0, max_rows)
