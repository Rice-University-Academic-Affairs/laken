from dataclasses import dataclass


def table_name_parts(name: str) -> list[str]:
    if not name or not name.strip():
        raise ValueError("table name must be non-empty")
    return name.strip().split(".")


@dataclass(frozen=True)
class TableRef:
    schema: str
    table: str

    def metadata_key(self) -> str:
        if self.schema == "dbo":
            return self.table
        return format_table_name(self.schema, self.table)


def parse_table_ref(name: str) -> TableRef:
    parts = table_name_parts(name)
    if len(parts) == 1:
        return TableRef(schema="dbo", table=parts[0])
    if len(parts) == 2:
        return TableRef(schema=parts[0], table=parts[1])
    raise ValueError(
        f"unsupported table name format: {name!r} (use 'table' or 'schema.table')"
    )


def parse_table_name(name: str) -> tuple[str, str]:
    ref = parse_table_ref(name)
    return ref.schema, ref.table


def format_table_name(schema: str, table: str) -> str:
    return f"{schema}.{table}"


def format_fabric_table_name(
    workspace_name: str,
    lakehouse: str,
    schema: str,
    table: str,
) -> str:
    return f"{workspace_name}.{lakehouse}.{schema}.{table}"


def spark_table_name(ref: TableRef) -> str:
    if ref.schema == "dbo":
        return ref.table
    return format_table_name(ref.schema, ref.table)
