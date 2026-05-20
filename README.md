# laken

Testable lakehouse code for Microsoft Fabric — develop locally with parquet, deploy with Spark.

## Install

```bash
uv add laken
```

## Deploy to Fabric

Install `uv`, then run `laken` from the root of the application repo you want to deploy:

```bash
cd myapp
cp .env.example .env
laken deploy
```

`laken deploy` clears `dist/`, builds the caller's wheel once with `uv build`, uploads the
single matching wheel from `dist/` to the configured Fabric environment staging area, and
submits publish (HTTP 200 upload, HTTP 202 publish accepted). The command does not poll for
publish completion.

Required configuration can be supplied in `.env` or through the process environment:

| Name | Description |
| --- | --- |
| `AZURE_TENANT_ID` | Azure tenant for client-credentials auth |
| `AZURE_CLIENT_ID` | Azure application client id |
| `AZURE_CLIENT_SECRET` | Azure application client secret |
| `FABRIC_WORKSPACE_ID` | Fabric workspace id |
| `FABRIC_ENVIRONMENT_ID` | Fabric environment id |

Use flags to override the Fabric target without changing `.env`:

```bash
laken deploy --workspace-id <workspace-id> --environment-id <environment-id>
```

For CI, provide configuration through environment variables and run deploy:

```bash
export AZURE_TENANT_ID=<tenant-id>
export AZURE_CLIENT_ID=<client-id>
export AZURE_CLIENT_SECRET=<client-secret>
export FABRIC_WORKSPACE_ID=<workspace-id>
export FABRIC_ENVIRONMENT_ID=<environment-id>
laken deploy
```

- `laken deploy` clears `dist/`, builds once, and uploads the single wheel matching
  `[project].name`; the version shown in success output comes from the built wheel filename.

Caller repos should contain one application package and run commands from the directory
containing `pyproject.toml`. Fabric must already have a compatible Python and Spark
runtime, and the caller package should depend on `laken` in its own `pyproject.toml`.

`laken` uploads the wheel exactly as built. With hatchling and a `src/` layout, configure
wheel packages so test files are not included:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/myapp"]
```

## Local development

```python
from laken import Lakehouse

lh = Lakehouse()

lh.write_table(df, "products")
lh.write_table(df, "marketing.products")

result = lh.read_table("products", as_="polars")
```

## Files (parquet)

```python
lh.write_file(df, "exports/summary.parquet")
summary = lh.read_file("exports/summary.parquet", as_="pandas")
```

## Fabric notebooks

```python
from laken import Lakehouse

lh = Lakehouse()

lh.write_table(df, "products", mode="overwrite")
spark_df = lh.read_table("products")
```

Cross-lakehouse (pass lakehouse explicitly; workspace id/name default from notebook context):

```python
lh = Lakehouse(lakehouse="Sales_LH")
lh.read_table("marketing.products", as_="pandas")
```

## Local vs Fabric

- **Lakehouse**: automatically delegates to Fabric in Fabric notebooks, otherwise local parquet
- **LocalLakehouse**: parquet under `./lakehouse` — no Delta ACID or time travel
- **FabricLakehouse**: Delta tables + Spark; `notebookutils` provided by the Fabric runtime

## Development

```bash
uv sync
uv run pytest
uv run ruff check
uv build
```
