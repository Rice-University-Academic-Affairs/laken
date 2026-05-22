from dataclasses import dataclass


def table_name_parts(name: str) -> list[str]:
    if not name or not name.strip():
        raise ValueError("table name must be non-empty")
    return name.strip().split(".")


def is_four_part_table_name(name: str) -> bool:
    return len(table_name_parts(name)) == 4


@dataclass(frozen=True)
class TableRef:
    schema: str
    table: str
    workspace: str | None = None
    lakehouse: str | None = None

    def fabric_four_part(self) -> str:
        if not self.workspace or not self.lakehouse:
            raise ValueError("fabric four-part name requires workspace and lakehouse")
        return format_fabric_table_name(self.workspace, self.lakehouse, self.schema, self.table)

    def metadata_key(self) -> str:
        if self.schema == "dbo":
            return self.table
        return format_table_name(self.schema, self.table)


def resolve_table_ref(
    name: str,
    *,
    workspace_name: str | None = None,
    workspace_id: str | None = None,
    lakehouse_name: str | None = None,
    lakehouse_id: str | None = None,
) -> TableRef:
    parts = table_name_parts(name)
    if len(parts) == 1:
        return TableRef(schema="dbo", table=parts[0])
    if len(parts) == 2:
        return TableRef(schema=parts[0], table=parts[1])
    if len(parts) == 3:
        workspace_keys = {workspace_name, workspace_id} - {None}
        if workspace_keys and parts[0] in workspace_keys:
            return TableRef(
                workspace=parts[0],
                lakehouse=parts[1],
                schema="dbo",
                table=parts[2],
            )
        lakehouse_keys = {lakehouse_name, lakehouse_id} - {None}
        if lakehouse_keys and parts[0] in lakehouse_keys:
            return TableRef(
                lakehouse=parts[0],
                schema=parts[1],
                table=parts[2],
            )
        return TableRef(lakehouse=parts[0], schema=parts[1], table=parts[2])
    if len(parts) == 4:
        return TableRef(
            workspace=parts[0],
            lakehouse=parts[1],
            schema=parts[2],
            table=parts[3],
        )
    raise ValueError(f"unsupported table name format: {name}")


def parse_table_name(name: str) -> tuple[str, str]:
    ref = resolve_table_ref(name)
    return ref.schema, ref.table


def to_spark_table_name(ref: TableRef, *, explicit_lakehouse: bool) -> str:
    if explicit_lakehouse:
        return ref.fabric_four_part()
    if ref.schema == "dbo":
        return ref.table
    return format_table_name(ref.schema, ref.table)


def resolve_spark_table_name(name: str) -> str:
    stripped = name.strip()
    parts = table_name_parts(stripped)
    if len(parts) in {1, 2, 3, 4}:
        return stripped
    raise ValueError(f"unsupported table name format: {name}")


def format_table_name(schema: str, table: str) -> str:
    return f"{schema}.{table}"


def format_fabric_table_name(workspace_name: str, lakehouse: str, schema: str, table: str) -> str:
    return f"{workspace_name}.{lakehouse}.{schema}.{table}"
