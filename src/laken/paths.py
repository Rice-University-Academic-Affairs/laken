def table_name_parts(name: str) -> list[str]:
    if not name or not name.strip():
        raise ValueError("table name must be non-empty")
    return name.strip().split(".")


def is_four_part_table_name(name: str) -> bool:
    return len(table_name_parts(name)) == 4


def parse_table_name(name: str) -> tuple[str, str]:
    parts = table_name_parts(name)
    if len(parts) == 1:
        return "dbo", parts[0]
    if len(parts) == 2:
        return parts[0], parts[1]
    if len(parts) == 4:
        return parts[2], parts[3]
    raise ValueError(f"unsupported table name format: {name}")


def require_qualified_table_name(name: str) -> tuple[str, str]:
    parts = table_name_parts(name)
    if len(parts) == 1:
        raise ValueError("write_table requires schema.table; bare table names are not supported")
    if len(parts) == 2:
        return parts[0], parts[1]
    if len(parts) == 4:
        return parts[2], parts[3]
    raise ValueError(f"unsupported table name format: {name}")


def format_table_name(schema: str, table: str) -> str:
    return f"{schema}.{table}"


def format_fabric_table_name(workspace_name: str, lakehouse: str, schema: str, table: str) -> str:
    return f"{workspace_name}.{lakehouse}.{schema}.{table}"
