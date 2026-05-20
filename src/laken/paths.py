def parse_table_name(name: str) -> tuple[str, str]:
    if not name or not name.strip():
        raise ValueError("table name must be non-empty")
    parts = name.strip().split(".", 1)
    if len(parts) == 1:
        return "dbo", parts[0]
    return parts[0], parts[1]


def format_table_name(schema: str, table: str) -> str:
    return f"{schema}.{table}"
