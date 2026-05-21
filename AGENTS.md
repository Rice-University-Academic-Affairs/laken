# laken — agent instructions

## What this repo is

Python library for testable lakehouse code on Microsoft Fabric (local parquet, Fabric/Spark in notebooks). This repo develops **laken** itself — `src/laken/`, tests, and packaging — not a separate app that consumes it.

```
src/laken/          lakehouse, local, fabric, frames, cli, deploy/
tests/              mirrors package; tests/deploy/ for deploy CLI
pyproject.toml      metadata, ruff, pytest; dev deps in [dependency-groups] dev
```

## Environment

Use the **same Linux commands** everywhere: Cursor Cloud, Linux CI, and local **WSL bash** at repo root (`pyproject.toml`, `uv.lock` present).

| Where | Shell | Commands |
|-------|--------|----------|
| Cursor Cloud / Linux | bash | `uv sync`, `uv run pytest`, … |
| Windows | WSL bash (`/mnt/c/.../laken`) | same |
| Forbidden | PowerShell/cmd on `C:\...` | native Windows `uv` replaces Unix `.venv` with `Lib/`/`Scripts/` |

Bootstrap:

1. [uv](https://docs.astral.sh/uv/) on `PATH`
2. Python **3.11** (`.python-version`)
3. `uv sync` on first use and after `pyproject.toml` / `uv.lock` changes

`.venv` must be Unix (`bin/`, `lib/`). Never delete or recreate `.venv` unless the user explicitly asks. If sync fails, report the error — do not wipe the venv.

If the agent shell on Windows is not WSL:

```bash
wsl -e bash -lc 'cd /mnt/c/Users/codya/Desktop/Projects/laken && uv sync'
```

(Adjust the path to this repo.)

Do not edit `.venv/`, `dist/`, `build/`, `*.egg-info/`, `.pytest_cache/`, `.ruff_cache/`, or local lakehouse/Spark artifact dirs.

## Commands

Use `uv run` — not bare `pytest`/`ruff` or `pip install -e .` unless the user asks.

| Task | Command |
|------|---------|
| Install / refresh | `uv sync` |
| All tests | `uv run pytest` |
| Deploy code only | `uv run pytest tests/deploy -q` |
| Lint | `uv run ruff check` |
| Format | `uv run ruff format` |
| Build wheel | `uv build` |

Step-by-step: `.cursor/skills/` — `/sync-dev-env`, `/run-tests`, `/run-lint`, `/build-package`.

## Developing this package

- Edit only under `src/` and `tests/`
- After `src/laken/deploy/` changes: `uv run pytest tests/deploy -q`; otherwise `uv run pytest`
- Match Ruff in `pyproject.toml` (line length 100, `py311`)
- Minimal diffs; no docstrings or comments unless the user asks
- Do not run live `laken deploy` against real Fabric unless the user explicitly asks
- Tests are mocked; no live Fabric credentials required for pytest

Human docs: [README.md](README.md).

## Cursor Cloud specific instructions

Cloud Agent VMs may have Fabric-related secrets injected as environment variables (`FABRIC_WORKSPACE_NAME`, `FABRIC_LAKEHOUSE_NAME`, `FABRIC_WORKSPACE_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `FABRIC_ENVIRONMENT_ID`). These cause `LocalLakehouse` to resolve 4-part table names in tests, breaking the `FakeFabricFetcher` lookup. **Unset them when running pytest:**

```bash
env -u FABRIC_WORKSPACE_NAME -u FABRIC_LAKEHOUSE_NAME -u FABRIC_WORKSPACE_ID -u AZURE_TENANT_ID -u AZURE_CLIENT_ID -u AZURE_CLIENT_SECRET -u FABRIC_ENVIRONMENT_ID uv run pytest
```

Commands reference (see tables above for full list): `uv sync`, `uv run pytest`, `uv run ruff check`, `uv run ruff format`, `uv build`.
