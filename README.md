# laken

The missing local development workflow for Microsoft Fabric.

Develop Python for Fabric on your laptop with the tools you already use. Read real
lakehouse tables locally, run the same code in Fabric notebooks unchanged, and ship your
package with `laken deploy` when you are ready.

Keep code in a proper package, notebooks thin, and your local workflow intact.

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

## Develop against your lakehouse

Set Azure credentials and which workspace/lakehouse to mirror locally:

```env
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
FABRIC_WORKSPACE_NAME=MyWorkspace
FABRIC_LAKEHOUSE_NAME=MyLakehouse
```

Optional: `FABRIC_WORKSPACE_ID`, `FABRIC_LAKEHOUSE_ID`.

```python
from laken import Lakehouse

lh = Lakehouse()
products = lh.read_table("marketing.products", as_="pandas")

lh.write_table(products, "staging.products_snapshot")
```

On your laptop, the first `read_table` for a Fabric table pulls from OneLake and caches
under `.laken/` as Delta; later reads use the cache. Local `write_table` stays local. In
a Fabric notebook, the same calls use the attached lakehouse.

## Deploy to Fabric

Your repo is a normal Python package. `laken deploy` builds it and publishes the wheel to
a Fabric environment so notebooks can import it by name.

```
myapp/
├── pyproject.toml          # [project] name = "myapp"
├── src/
│   └── myapp/
│       ├── __init__.py
│       └── pipeline.py
└── .env
```

The import path must match `[project].name` in `pyproject.toml` (here, `myapp`). Use a
standard [src layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
and declare which packages go in the wheel — for example with hatchling:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/myapp"]
```

Add `laken` to your project dependencies. See the
[Python packaging guide](https://packaging.python.org/en/latest/tutorials/packaging-projects/)
if you are setting this up for the first time.

Deploy credentials (`.env` or shell):

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

In a Fabric notebook, import your module like any installed package:

```python
from myapp.pipeline import run_pipeline
from laken import Lakehouse

run_pipeline(Lakehouse())
```

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

**Tables** — `mode` is `"overwrite"` or `"append"`; bare names use schema `dbo`.

```python
lh.write_table(df, "products")
lh.write_table(df, "marketing.products", mode="append")

df = lh.read_table("products")                    # Spark
df = lh.read_table("products", as_="pandas")
df = lh.read_table("products", as_="polars")

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

`status`, `refresh`, and `reset` apply to the local `.laken/` cache.

### Configuration

| Variable | Purpose |
| --- | --- |
| `AZURE_TENANT_ID` | Auth (fetch + deploy) |
| `AZURE_CLIENT_ID` | Auth (fetch + deploy) |
| `AZURE_CLIENT_SECRET` | Auth (fetch + deploy) |
| `FABRIC_WORKSPACE_NAME` | Local table fetch |
| `FABRIC_LAKEHOUSE_NAME` | Local table fetch |
| `FABRIC_WORKSPACE_ID` | Optional OneLake IDs; required for deploy |
| `FABRIC_LAKEHOUSE_ID` | Optional OneLake IDs |
| `FABRIC_ENVIRONMENT_ID` | Deploy target |

Deploy expects `pyproject.toml` at the repo root, a buildable application wheel, and a
Fabric environment with a compatible Python/Spark runtime.

### Local vs Fabric

| Class | Where | Storage |
| --- | --- | --- |
| `Lakehouse` | Auto-detects notebook context | Fabric if available, else `.laken/` Delta |
| `LocalLakehouse` | Laptop / CI | `.laken/workspace/` |
| `FabricLakehouse` | Fabric notebook | Attached lakehouse |

First local read of a Fabric table fetches and caches Delta under `.laken/`. If Fabric
changes, `laken` warns and keeps the cache until you run `laken refresh <table>`. Large
tables may cache as a fixed-size sample. Local writes do not push to Fabric.

## Development

Contributors working on this repo:

```bash
uv sync
uv run pytest
uv run ruff check
```
