## Cursor Cloud specific instructions

This is a pure Python library (no web servers, databases, or Docker). All development commands are in the README `Development` section: `uv sync`, `uv run pytest`, `uv run ruff check`, `uv build`.

- **Java required**: PySpark depends on a JRE. The VM has `default-jdk-headless` installed. If tests fail with Java errors, verify `java -version` works.
- **Python 3.11**: The project pins Python 3.11 via `.python-version`. `uv` handles this automatically when `uv sync` is run.
- **No services to start**: All tests run locally against the filesystem using `LocalLakehouse` and mocks for `FabricLakehouse`. No external services or network access needed.
