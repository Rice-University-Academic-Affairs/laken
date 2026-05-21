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
| All tests (unit + integration) | `uv run pytest` |
| Unit tests only | `uv run pytest -m "not integration"` |
| Deploy code only | `uv run pytest tests/deploy -q` |
| Lint | `uv run ruff check` |
| Format | `uv run ruff format` |
| Build wheel | `uv build` or `make build` |
| Publish to PyPI | `make publish` (requires `PYPI_TOKEN`) |

Step-by-step: `.cursor/skills/` — `/sync-dev-env`, `/run-tests`, `/run-lint`, `/build-package`.

## Developing this package

- Edit only under `src/` and `tests/`
- **After any change to `src/` or `tests/`, run the full suite:** `uv run pytest` (unit and integration). Do not skip integration tests when credentials are available.
- Deploy-only shortcut: after `src/laken/deploy/` changes, `uv run pytest tests/deploy -q` is not enough by itself — still run `uv run pytest` before finishing.
- Match Ruff in `pyproject.toml` (line length 100, `py311`)
- Minimal diffs; no docstrings or comments unless the user asks
- Do not run live `laken deploy` against real Fabric unless the user explicitly asks

### Integration tests

27 tests under `tests/integration/` are marked `integration`. They run with `uv run pytest` (no extra flags). They need live Azure/Fabric env vars:

| Variable | Purpose |
|----------|---------|
| `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` | OAuth |
| `FABRIC_WORKSPACE_NAME`, `FABRIC_LAKEHOUSE_NAME` | OneLake paths |
| `FABRIC_WORKSPACE_ID`, `FABRIC_LAKEHOUSE_ID` | ID-based OneLake URIs |

If credentials are missing, those tests skip. If they are set (Cursor Cloud / CI with secrets), agents must run them and report pass/skip/fail.

Human docs: [README.md](README.md).
