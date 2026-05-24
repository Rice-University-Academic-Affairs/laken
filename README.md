<div align="center">

![laken](docs/laken_splash.png)

**The missing local development workflow for Microsoft Fabric.**

</div>

**laken** lets you develop Python code for Fabric locally, using the tools you already trust.

Write code on your machine, run it against real Fabric lakehouse tables (cached under `.laken/`).

When you're ready, `laken deploy` packages your project, publishes it to a Fabric Environment, and makes it
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

## Quickstart

**1. Credentials** — create a `.env` in your project root:

```env
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
FABRIC_WORKSPACE_NAME=MyWorkspace
FABRIC_LAKEHOUSE_NAME=MyLakehouse
FABRIC_WORKSPACE_ID=...
FABRIC_LAKEHOUSE_ID=...
```

**2. Develop locally** — first `read_table` pulls from Fabric and caches Delta under `.laken/`:

```python
from laken import Lakehouse

lh = Lakehouse()
df = lh.read_table("customers", frame_type="pandas")
lh.write_table(df, "customer_analytics")
```

In a Fabric notebook, the same calls use your attached lakehouse (Spark by default).

**3. Package and deploy** — standard `src/` layout plus `FABRIC_ENVIRONMENT_ID` in `.env`:

```bash
laken deploy
```

**4. Run in a notebook:**

```python
from laken import Lakehouse
from myapp.pipeline import run_pipeline

lh = Lakehouse()
run_pipeline(lh)
```

---

## Table names

Use a bare table name or `schema.table` (for example `products` or `marketing.products`).

Cross-lakehouse or multi-part Fabric names are not supported — use Spark directly in the
notebook for those reads.

---

## Local Fabric cache

Locally, the first `read_table` for a Fabric-backed table downloads into `.laken/` as Delta.
Later reads use the cache until you refresh or reset.

- Tables **100 MB or smaller** (from the Delta log) are mirrored in full.
- Larger tables cache the first **10,000 rows** as a development sample.

```python
lh = Lakehouse(max_mirror_mb=200, max_sample_rows=5_000)
```

Local writes stay under `.laken/` and do not sync to Fabric. Run `laken refresh <table>` when
you need the latest Fabric data. Run `laken reset <table>` to discard local edits and
re-download from Fabric.

Cache metadata is stored in `.laken/metadata/tables.json`.

---

## Deploy to Fabric

```
myapp/
├── pyproject.toml
├── src/myapp/pipeline.py
└── .env
```

```env
FABRIC_WORKSPACE_ID=...
FABRIC_ENVIRONMENT_ID=...
```

```bash
laken deploy
```

---

## Reference

### `Lakehouse`

```python
from laken import Lakehouse

lh = Lakehouse()
```

**Reads and writes** — `mode` is `"overwrite"` or `"append"`.

```python
df = lh.read_table("products")                         # pandas locally, Spark in Fabric
df = lh.read_table("marketing.products", frame_type="polars")
lh.write_table(df, "staging.products_snapshot")
```

### CLI

```text
laken deploy [--workspace-id <id>] [--environment-id <id>]
laken refresh <table>
laken reset <table>
```

### Environment variables

Loaded from `.env` when you construct `Lakehouse` or run the CLI (shell variables win).

| Variable | Purpose |
| :--- | :--- |
| `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` | Auth |
| `FABRIC_WORKSPACE_NAME`, `FABRIC_LAKEHOUSE_NAME` | Local Fabric fetch |
| `FABRIC_WORKSPACE_ID`, `FABRIC_LAKEHOUSE_ID` | OneLake paths |
| `FABRIC_ENVIRONMENT_ID` | Deploy target |

### Testing

Inject a fetcher in unit tests:

```python
from laken.local_lakehouse import LocalLakehouse
```

---

## Development

```bash
uv sync
uv run pytest
uv run ruff check
```
