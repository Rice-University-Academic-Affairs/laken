## Cursor Cloud specific instructions

This is a pure Python library (no web servers, databases, or Docker). All development commands are in the README `Development` section: `uv sync`, `uv run pytest`, `uv run ruff check`, `uv build`.

- **No Java needed**: Although `pyspark` is a dependency, all Spark usage in tests is fully mocked. No JDK/JRE is required for local development or testing.
- **Python 3.11**: The project pins Python 3.11 via `.python-version`. `uv` handles this automatically when `uv sync` is run.
- **No services to start**: All tests run locally against the filesystem using `LocalLakehouse` and mocks for `FabricLakehouse`. No external services or network access needed.
