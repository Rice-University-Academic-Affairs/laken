<div align="center">

# laken

**The missing local development workflow for Microsoft Fabric.**

[![Python](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/laken.svg)](https://pypi.org/project/laken/)
[![Microsoft Fabric](https://img.shields.io/badge/Microsoft-Fabric-0078D4?logo=microsoft&logoColor=white)](https://www.microsoft.com/microsoft-fabric)

</div>

<br>

**laken** lets you develop Python code for Fabric locally, using the tools you already trust.

Write code on your machine, run it against real Fabric lakehouse data.

When you're ready, `laken deploy` packages your project, publishes it to Fabric, and makes it
available to your Fabric notebooks.

Your code stays modular. Your notebooks stay thin. And your local workflow survives contact
with the platform.

## Why “laken”?

*Laken*, pronounced **LAH-kuhn**, is Dutch for “cloth.” If you're feeling generous, it's a pun
on Fabric and data lakes.

---

## Installation

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if needed, then add
`laken`:

```bash
uv add laken
```

```bash
pip install laken
```

Deploy uses [uv](https://docs.astral.sh/uv/getting-started/installation/) to build your
wheel before publishing to a Fabric environment.

---

## Develop against your Fabric lakehouse

Set your credentials, select your workspace and lakehouse in a `.env` file at your
project root (or export them in your shell). Importing `laken` loads that file
automatically; variables already set in the environment are not overwritten.

```env
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
FABRIC_WORKSPACE_NAME=MyWorkspace
FABRIC_LAKEHOUSE_NAME=MyLakehouse
FABRIC_WORKSPACE_ID=...
FABRIC_LAKEHOUSE_ID=...
```

```python
from laken import Lakehouse

lh = Lakehouse()
products = lh.read_table("marketing.products", as_="pandas")

lh.write_table(products, "staging.products_snapshot")
```

`Lakehouse` detects when it is running locally and when it is running inside Fabric.

Locally, the first `read_table` for a Fabric table pulls from OneLake and caches it under
`.laken/` as Delta; later reads use the cache. In a Fabric notebook, the same code reads
from your attached lakehouse.

Local writes stay under `.laken/` and do not sync to Fabric; in Fabric, writes persist to
tables on the attached lakehouse.

---

## Deploy to Fabric

Structure your local code as a Python project using the standard
[src layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/):

```
myapp/
├── pyproject.toml          # [project] name = "myapp"
├── src/
│   └── myapp/
│       ├── __init__.py
│       └── pipeline.py
└── .env
```

Add `laken` to your project dependencies. 

See the
[Python packaging guide](https://packaging.python.org/en/latest/tutorials/packaging-projects/)
if you are setting this up for the first time.

```python
# src/myapp/pipeline.py
import pandas as pd

from laken import Lakehouse


def run_pipeline(lh: Lakehouse) -> None:
    products = lh.read_table("marketing.products", as_="pandas")
    summary = products.groupby("category", as_index=False)["amount"].sum()
    lh.write_table(summary, "staging.product_summary")
```

When you are ready, `laken deploy` builds your package and loads it into your specified
Fabric Environment.

Deploy uses the same `.env` (or shell variables):

```env
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
FABRIC_WORKSPACE_ID=...
FABRIC_ENVIRONMENT_ID=...
```

From the repo root:

```bash
laken deploy
```

In a Fabric notebook:

```python
from laken import Lakehouse
from myapp.pipeline import run_pipeline

lh = Lakehouse()
run_pipeline(lh)
```

---

## Reference

### `Lakehouse`

```python
from laken import Lakehouse

lh = Lakehouse()
```

For tests or scripts that must pin a backend:

```python
from laken import FabricLakehouse, LocalLakehouse
```

**Tables** — use `schema.table` to target a schema; a bare name is passed through to Spark
and Fabric resolves it (typically the default `dbo` schema on a schema-enabled lakehouse).
`mode` is `"overwrite"` or `"append"`.

```python
lh.write_table(df, "products")
lh.write_table(df, "marketing.products", mode="append")

df = lh.read_table("products")                    # pandas locally, Spark in Fabric
df = lh.read_table("products", as_="spark")       # Spark (Fabric runtime)
df = lh.read_table("marketing.products", as_="polars")

lh.list_tables()
lh.table_exists("marketing.products")
lh.drop_table("marketing.products")
```

**Files** — local paths under `.laken/workspace/Files`; in Fabric, under the lakehouse
`Files/` area.

```python
lh.write_file(df, "exports/summary.parquet")
lh.read_file("exports/summary.parquet", as_="pandas")
lh.list_files("exports")
lh.file_exists("exports/summary.parquet")
lh.delete_file("exports/summary.parquet")
```

**Warehouse tables** — Spark `synapsesql` in Fabric; local parquet stand-in for tests.

```python
lh.load_table_from_warehouse("SalesOrderHeader", "SalesWarehouse", as_="pandas")
```

**Other lakehouses** — defaults come from notebook context in Fabric; override locally
or in notebooks:

```python
lh = Lakehouse(lakehouse="Sales_LH")
lh.read_table("marketing.products", as_="pandas")
```

### CLI

```text
laken deploy [--workspace-id <id>] [--environment-id <id>]
laken status
laken refresh <table>
laken reset <table>
```

`laken deploy` builds the wheel from your repo's `pyproject.toml`, uploads it to a Fabric
Environment, and publishes it so notebooks can import your package.

`laken status`, `laken refresh`, and `laken reset` manage the local `.laken/` cache on your
laptop. They do not run inside Fabric notebooks.

`laken status` lists cached tables with state (`mirror`, `sample`, or `local`), the Fabric
source version when known, and notes such as staleness or sample size.

`laken refresh <table>` re-downloads a table from Fabric when it was originally cached
from Fabric. Local-only tables are left unchanged.

`laken reset <table>` discards local changes and re-fetches from Fabric. The table must
have been cached from Fabric first.

### Environment variables

Root `.env` is loaded when you `import laken` or run the `laken` CLI. Shell and CI
variables take precedence. Set `PYTHON_DOTENV_DISABLED=1` to skip loading.

| Variable | Purpose |
| :--- | :--- |
| `AZURE_TENANT_ID` | Auth (fetch + deploy) |
| `AZURE_CLIENT_ID` | Auth (fetch + deploy) |
| `AZURE_CLIENT_SECRET` | Auth (fetch + deploy) |
| `FABRIC_WORKSPACE_NAME` | Local table fetch |
| `FABRIC_LAKEHOUSE_NAME` | Local table fetch |
| `FABRIC_WORKSPACE_ID` | OneLake paths; required for deploy |
| `FABRIC_LAKEHOUSE_ID` | OneLake paths |
| `FABRIC_ENVIRONMENT_ID` | Deploy target |

`AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, and `AZURE_CLIENT_SECRET` are credentials from an
Azure service principal.

`FABRIC_WORKSPACE_NAME`, `FABRIC_LAKEHOUSE_NAME`, `FABRIC_WORKSPACE_ID`,
`FABRIC_LAKEHOUSE_ID`, and `FABRIC_ENVIRONMENT_ID` can be read from a Fabric notebook with
`notebookutils`:

```python
import notebookutils

ctx = notebookutils.runtime.context
print(ctx.get("currentWorkspaceName"))
print(ctx.get("currentWorkspaceId"))
print(ctx.get("defaultLakehouseName"))
print(ctx.get("defaultLakehouseId"))
print(ctx.get("environmentId"))
```

Deploy expects `pyproject.toml` at the repo root, a buildable application wheel, and a
Fabric environment with a compatible Python/Spark runtime.

### Local vs Fabric

| Class | Where | Storage | Reads | Writes |
| :--- | :--- | :--- | :--- | :--- |
| `Lakehouse` | Auto-detects notebook context | Fabric if available, else `.laken/` Delta | Local: Fabric → cache; Fabric: attached lakehouse | Local: `.laken/` only; Fabric: attached lakehouse |
| `LocalLakehouse` | Laptop / CI | `.laken/workspace/` | Cached Delta and local tables | Local only; not pushed to Fabric |
| `FabricLakehouse` | Fabric notebook | Attached lakehouse | Spark/Delta on attached lakehouse | Delta tables on attached lakehouse |

First local read of a Fabric table fetches and caches Delta under `.laken/`. Tables up to
**100 MB** on Fabric (from the Delta transaction log) are mirrored in full; larger tables
cache up to **10,000 rows** as a development sample. Override on `Lakehouse` construction or
per `read_table` call:

```python
lh = Lakehouse(max_mirror_mb=200, max_sample_rows=5_000)
lh.read_table("dbo.big_fact", max_mirror_mb=500)
```

Per-read overrides apply only on the first hydrate; refresh and reset use the instance
defaults. If Fabric changes, `laken` warns and keeps the cache until you run
`laken refresh <table>`.

---

## Development

Contributions are welcome. To work on this package:

```bash
uv sync
uv run pytest
uv run ruff check
```
