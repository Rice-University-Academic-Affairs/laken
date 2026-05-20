# laken — agent instructions

## What this repo is

**laken** is a Python library for testable lakehouse code on Microsoft Fabric: develop locally with parquet, use Spark in Fabric notebooks. It also ships a Typer CLI for building wheels and publishing to Fabric environments (`laken deploy`, `laken build`, `laken upload`).

## Repository map

```
pyproject.toml          # package metadata, uv dev group, ruff/pytest config
uv.lock                 # lockfile — commit with dependency changes
.python-version         # 3.11

src/laken/
  __init__.py           # public exports (Lakehouse, LocalLakehouse, …)
  lakehouse.py          # facade — local vs Fabric routing
  local.py              # parquet under ./lakehouse
  fabric.py             # Delta + Spark in Fabric runtime
  frames.py, paths.py, types.py, protocol.py
  cli.py                # Typer entrypoint
  deploy/               # wheel build, config, Fabric HTTP client
    build.py, config.py, fabric_client.py, project.py, wheel.py

tests/                  # lakehouse / frames / paths tests
tests/deploy/           # deploy CLI unit tests (mocked HTTP)
tests/conftest.py       # shared fixtures (lakehouse, sample_df, …)
```

## Environment

- Install [uv](https://docs.astral.sh/uv/) in **WSL** (primary dev environment).
- Python **3.11** (see `.python-version`).
- Repo on disk: `C:\Users\...\laken` → use WSL path `/mnt/c/Users/.../laken` for all commands.
- On first use or after dependency changes, from **WSL bash** at repo root:

```bash
uv sync
```

Dev tools (`pytest`, `ruff`) are in `[dependency-groups] dev` — not installed by `pip install laken` alone.

### `.venv` layout (Unix — required)

- **Correct:** `bin/`, `lib/python3.11/site-packages/`, `pyvenv.cfg` with a Linux (or WSL) Python path.
- **Wrong for this repo:** `Lib/`, `Scripts/`, `cpython-*-windows-*` in `pyvenv.cfg` — created when something runs **native Windows** `uv` on `C:\...`. That breaks WSL workflows and causes `lib64` / access-denied errors on the next sync.
- **Agents must not** delete or recreate `.venv` when sync fails. Report the error instead.
- **Agents on a Windows host** must run `uv` only via WSL (`wsl -e bash -lc '…'`) or `.cursor/scripts/*.py` (WSL-aware). Do not use PowerShell `uv sync` / `uv run`.
- Cursor terminal default for this workspace: WSL (see `.vscode/settings.json`).

## Common commands

Use `uv run` so tools run inside the project venv. Do not use bare `pytest`, `ruff`, or `pip install -e .` unless explicitly asked.

| Task | Command |
|------|---------|
| Install / refresh env | `uv sync` |
| All tests | `uv run pytest` |
| Deploy tests only | `uv run pytest tests/deploy -q` |
| Lint | `uv run ruff check` |
| Format (optional fix) | `uv run ruff format` |
| Build wheel | `uv build` |

Cursor skills with step-by-step workflows: `.cursor/skills/` (`sync-dev-env`, `run-tests`, `run-lint`, `build-package`). Invoke with `/skill-name` or let Agent pick them up from context.

Optional wrappers: `.cursor/scripts/` (`run_tests.py`, `run_lint.py` — route through WSL on Windows). From PowerShell, do **not** use `uv run python .cursor/...` (Windows uv runs first). Use:

```bash
wsl -e bash -lc "cd '/mnt/c/Users/codya/Desktop/Projects/laken' && uv run python .cursor/scripts/run_tests.py -q"
```

Or run `uv run pytest` / `uv run ruff` directly inside WSL bash.

## Secrets and integration

Fabric deploy needs Azure/Fabric variables (see `.env.example`). Copy to `.env` locally; **never commit** `.env` or secrets.

Most tests are unit tests with mocks — no live Fabric workspace required for `uv run pytest`.

Do not run `laken deploy` against real environments unless the user explicitly asks.

## Do not edit

- `.venv/` — never delete or recreate via automation; never edit files inside
- `dist/`, `build/`, `*.egg-info/`
- `.pytest_cache/`, `.ruff_cache/`
- Generated local data: `.lakehouse/`, `lakehouse/`, Spark metastore dirs

## More detail

- Conventions and layout: `.cursor/rules/`
- Runnable workflows: `.cursor/skills/`
- Human-oriented docs: `README.md`
