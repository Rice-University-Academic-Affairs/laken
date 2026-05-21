# laken

The missing local development workflow for Microsoft Fabric.

`laken` lets you develop Python code for Fabric locally, using the tooling you
already trust.

Write local code against real lakehouse data. The same code runs in Fabric
without modification.

When you're ready, `laken deploy` packages your project, publishes it to Fabric,
and makes it available to your Fabric notebooks.

Keep your code modular, your notebooks thin, and your local workflow intact.

## Installation

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if you do not have it
yet, then:

```bash
uv add laken
```

or:

```bash
pip install laken
```

`laken deploy` expects [uv](https://docs.astral.sh/uv/getting-started/installation/) on
`PATH` because it builds your application package before publishing it to Fabric.

## Develop against your lakehouse

Point `laken` at your Fabric workspace and lakehouse, then use the same
`Lakehouse` API locally and in notebooks. On your laptop, the first read of a
Fabric table pulls it from OneLake and caches it under `.laken/` as Delta. Later
reads stay fast and offline-friendly.

Add credentials and Fabric targets to `.env` (or your shell environment):

```env
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
FABRIC_WORKSPACE_NAME=MyWorkspace
FABRIC_LAKEHOUSE_NAME=MyLakehouse
```

Optional: `FABRIC_WORKSPACE_ID` and `FABRIC_LAKEHOUSE_ID` for ID-based OneLake paths.

```python
import polars as pl

from laken import Lakehouse

lh = Lakehouse()

products = lh.read_table("marketing.products", as_="polars")

enriched = products.with_columns(
    margin_pct=(pl.col("revenue") - pl.col("cost")) / pl.col("revenue"),
)

lh.write_table(enriched, "marketing.products_enriched")
```

Run that on your laptop: `read_table` hydrates from Fabric when needed; `write_table`
stays in your local `.laken/workspace`. Run the same module in a Fabric notebook and
`Lakehouse()` talks to the attached lakehouse with no code changes.

## Deploy to Fabric

From your application repo root (the directory with `pyproject.toml`):

```env
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
FABRIC_WORKSPACE_ID=...
FABRIC_ENVIRONMENT_ID=...
```

```bash
laken deploy
```

`laken deploy` builds your wheel with `uv`, uploads it to the Fabric environment, and
waits for the publish to be accepted. Your notebooks can import the package you just
shipped.

```python
from myapp.reports import build_summary
from laken import Lakehouse

summary = build_summary(Lakehouse())
display(summary)
```

Keep business logic in your package; keep the notebook as a thin entry point.

## Reference

### Python API

Import the automatic dispatcher for most application code:

```python
from laken import Lakehouse
```

Use explicit implementations when tests or scripts need a fixed backend:

```python
from laken import FabricLakehouse, LocalLakehouse
```

#### Tables

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

#### Files

```python
lh.write_file(df, "exports/summary.parquet")

spark_df = lh.read_file("exports/summary.parquet")
pandas_df = lh.read_file("exports/summary.parquet", as_="pandas")

files = lh.list_files("exports")
exists = lh.file_exists("exports/summary.parquet")
lh.delete_file("exports/summary.parquet")
```

Local files live under `.laken/workspace/Files`. Fabric files resolve under the active
lakehouse's `Files/` area.

#### Warehouses

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

#### Cross-lakehouse reads and writes

```python
lh = Lakehouse(lakehouse="Sales_LH")
df = lh.read_table("marketing.products", as_="pandas")
```

Inside Fabric, workspace and lakehouse defaults come from notebook context. Pass
`lakehouse`, `workspace_id`, or `workspace_name` when you need to target another
lakehouse explicitly.

### CLI

```text
laken deploy [--workspace-id <workspace-id>] [--environment-id <environment-id>]
laken status
laken refresh <table>
laken reset <table>
```

`status`, `refresh`, and `reset` operate on the project-local `.laken/` workspace.

Override the Fabric target for one deploy without changing `.env`:

```bash
laken deploy --workspace-id <workspace-id> --environment-id <environment-id>
```

| Name | Used by |
| --- | --- |
| `AZURE_TENANT_ID` | Lakehouse fetch and deploy |
| `AZURE_CLIENT_ID` | Lakehouse fetch and deploy |
| `AZURE_CLIENT_SECRET` | Lakehouse fetch and deploy |
| `FABRIC_WORKSPACE_NAME` | Local fetch (with `FABRIC_LAKEHOUSE_NAME`) |
| `FABRIC_LAKEHOUSE_NAME` | Local fetch |
| `FABRIC_WORKSPACE_ID` | Optional ID-based OneLake paths; required for deploy |
| `FABRIC_LAKEHOUSE_ID` | Optional ID-based OneLake paths |
| `FABRIC_ENVIRONMENT_ID` | Deploy target environment |

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

### Local vs Fabric behavior

| Class | Runtime | Storage |
| --- | --- | --- |
| `Lakehouse` | Auto-detects Fabric notebook context | Fabric when available, otherwise local Delta |
| `LocalLakehouse` | Any Python process | `.laken/workspace/Files` and `.laken/workspace/Tables` |
| `FabricLakehouse` | Fabric notebook or Spark runtime | Fabric lakehouse files and Delta tables |

In local mode, `laken` reads and writes Delta tables in a project-local workspace under
`.laken/`. The first time your code reads a Fabric lakehouse table, `laken` fetches
that table from Fabric and stores it locally as Delta. Later reads use the local copy,
so your development environment stays stable and fast.

If the Fabric source changes, `laken` warns you that your local copy is stale. It does
not replace local data automatically. Run `laken refresh <table>` when you want to
update your local copy. Large tables are cached as fixed-size development samples and
clearly marked as sampled.

Local writes stay local. In Fabric, the same `read_table` and `write_table` calls
resolve to the attached lakehouse.

## Development

For contributors working on this repository:

```bash
uv sync
uv run pytest
uv run ruff check
```
