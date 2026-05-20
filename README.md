# laken

Testable lakehouse code for Microsoft Fabric.

Build data code once, exercise it locally against parquet, then run the same package in
Fabric notebooks and Spark jobs. `laken` keeps the local loop small without hiding the
lakehouse model you ship to production.

## Why laken?

- One Python API for local parquet and Fabric lakehouses
- Pandas, Polars, and Spark DataFrame support
- Schema-qualified table names like `marketing.products`
- Local file/table helpers that mirror Fabric's `Files/` and `Tables/` layout
- A single CLI command, `laken deploy`, for publishing packages to Fabric environments

## Installation

```bash
uv add laken
```

or:

```bash
pip install laken
```

`laken deploy` expects `uv` on `PATH` because it builds your application package before
publishing it to Fabric.

## Getting started

```python
import pandas as pd

from laken import Lakehouse

lh = Lakehouse()

products = pd.DataFrame(
    {
        "id": [1, 2],
        "name": ["Widget", "Gadget"],
    }
)

lh.write_table(products, "marketing.products")

result = lh.read_table("marketing.products", as_="polars")
```

Run that code on your laptop and `Lakehouse()` writes parquet under `./lakehouse`.
Run the same code inside Fabric and `Lakehouse()` uses the attached Fabric lakehouse.

## Deploy to Fabric

From the root of the application repo you want to deploy:

```bash
laken deploy
```

`laken deploy` builds your wheel, publishes it to the configured Fabric environment, and
waits for the publish request to be accepted.

Required configuration can be supplied in `.env` or through the process environment:

| Name | Description |
| --- | --- |
| `AZURE_TENANT_ID` | Azure tenant for client-credentials auth |
| `AZURE_CLIENT_ID` | Azure application client id |
| `AZURE_CLIENT_SECRET` | Azure application client secret |
| `FABRIC_WORKSPACE_ID` | Fabric workspace id |
| `FABRIC_ENVIRONMENT_ID` | Fabric environment id |

Override the Fabric target for one deploy without changing `.env`:

```bash
laken deploy --workspace-id <workspace-id> --environment-id <environment-id>
```

Your application repo should:

- contain a `pyproject.toml` at the command root
- declare `laken` as a dependency
- build one application package for Fabric to install
- target a Fabric environment with a compatible Python and Spark runtime

With hatchling and a `src/` layout, configure wheel packages so tests and local files do
not land in the deployed wheel:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/myapp"]
```

### CLI reference

```text
laken deploy [--workspace-id <workspace-id>] [--environment-id <environment-id>]
```

`deploy` is the only supported CLI command.

## Python API

Import the automatic dispatcher for most application code:

```python
from laken import Lakehouse
```

Use explicit implementations when tests or scripts need a fixed backend:

```python
from laken import FabricLakehouse, LocalLakehouse
```

### Tables

```python
lh.write_table(df, "products")
lh.write_table(df, "marketing.products", mode="append")

spark_df = lh.read_table("products")
pandas_df = lh.read_table("products", as_="pandas")
polars_df = lh.read_table("products", as_="polars")

tables = lh.list_tables()
exists = lh.table_exists("marketing.products")
lh.drop_table("marketing.products")
```

`mode` can be `"overwrite"` or `"append"`. Unqualified table names use the `dbo` schema.

### Files

```python
lh.write_file(df, "exports/summary.parquet")

spark_df = lh.read_file("exports/summary.parquet")
pandas_df = lh.read_file("exports/summary.parquet", as_="pandas")

files = lh.list_files("exports")
exists = lh.file_exists("exports/summary.parquet")
lh.delete_file("exports/summary.parquet")
```

Local files live under `./lakehouse/Files`. Fabric files resolve under the active
lakehouse's `Files/` area.

### Warehouses

```python
df = lh.load_table_from_warehouse(
    "SalesOrderHeader",
    "SalesWarehouse",
    schema="dbo",
    as_="pandas",
)
```

In Fabric, this reads through Spark's `synapsesql` integration. Locally, it reads a
parquet file path so application code can stay testable without a live warehouse.

### Cross-lakehouse reads and writes

```python
lh = Lakehouse(lakehouse="Sales_LH")
df = lh.read_table("marketing.products", as_="pandas")
```

Inside Fabric, workspace and lakehouse defaults come from notebook context. Pass
`lakehouse`, `workspace_id`, or `workspace_name` when you need to target another
lakehouse explicitly.

## Local vs Fabric behavior

| Class | Runtime | Storage |
| --- | --- | --- |
| `Lakehouse` | Auto-detects Fabric notebook context | Fabric when available, otherwise local parquet |
| `LocalLakehouse` | Any Python process | `./lakehouse/Files` and `./lakehouse/Tables` |
| `FabricLakehouse` | Fabric notebook or Spark runtime | Fabric lakehouse files and Delta tables |

Local mode is intentionally lightweight: parquet files, no Delta transaction log, no
time travel, and no live Fabric credentials.

## Development

For contributors working on this repository:

```bash
uv sync
uv run pytest
uv run ruff check
```
