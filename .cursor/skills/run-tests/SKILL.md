---
name: run-tests
description: Run the laken test suite with uv and pytest. Use when verifying code changes, fixing failures, or before finishing a task.
---

# Run tests

## When to use

- After changing `src/` or `tests/`
- User asks to run tests or verify a fix
- Before considering a coding task complete

## Prerequisites

- Repo root as cwd
- Dev env synced: `uv sync` (run first if unsure)
- Cursor Cloud and Linux CI: use native Linux shell
- Windows hosts: use WSL bash for direct `uv` commands, not PowerShell

## Steps

1. Ensure dependencies are installed:

```bash
uv sync
```

2. Run tests (pick scope):

**Full suite (default):**

```bash
uv run pytest
```

**Quiet full suite:**

```bash
uv run pytest -q
```

**Deploy package only:**

```bash
uv run pytest tests/deploy -q
```

**Single file or node:**

```bash
uv run pytest tests/test_fabric_lakehouse.py -q
uv run pytest tests/deploy/test_wheel.py -q
```

**Extra pytest args:**

```bash
uv run pytest tests/deploy -q -k test_resolve
```

### Optional script

From repo root. The direct `uv run pytest` commands above are preferred on Linux, Cursor Cloud, macOS, and WSL. `.cursor/scripts/run_tests.py` is a small Python wrapper that resolves the repo root; when launched with Windows Python, it runs `uv` inside WSL automatically.

Linux / WSL:

```bash
uv run python .cursor/scripts/run_tests.py tests/deploy -q
```

Windows PowerShell:

```powershell
python .cursor\scripts\run_tests.py tests/deploy -q
```

Do not prefix the wrapper with Windows `uv`.

## Success criteria

- Exit code 0
- On failure: read traceback, fix source under `src/` or `tests/`, re-run — do not patch `.pytest_cache/`

## Do not

- `python -m pytest` or bare `pytest` without `uv run`
- Delete `.pytest_cache/` as a “fix” unless the user asks
