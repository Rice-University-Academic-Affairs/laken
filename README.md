# laken

Testable lakehouse code for Microsoft Fabric — develop locally with parquet, deploy with Spark.

## Install

```bash
uv add laken
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
