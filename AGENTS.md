## Cursor Cloud specific instructions

This is a Python library (not a running service). Development commands are in the README `## Development` section:

- `uv sync` — install/update all dependencies (including dev)
- `uv run pytest` — run test suite (55 tests, ~0.2s)
- `uv run ruff check` — lint
- `uv build` — build wheel/sdist

Python 3.11 is pinned in `.python-version`; `uv` manages the interpreter and virtualenv automatically.

PySpark runs in local mode — no external Spark cluster or Java install is needed beyond what `uv sync` provides. The Fabric-specific code paths (`FabricLakehouse`) are tested via mocks; they do not require a Microsoft Fabric environment.
