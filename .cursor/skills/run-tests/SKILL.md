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

- Repo root as cwd in **WSL bash** (on Windows: `/mnt/c/.../laken`, not PowerShell)
- Dev env synced: `uv sync` in WSL (run first if unsure)

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

**Extra pytest args** — pass after `--`:

```bash
uv run pytest tests/deploy -q -- -k test_resolve
```

### Optional script (WSL on Windows)

From repo root. On Windows hosts, `.cursor/scripts/run_tests.py` runs `uv` inside WSL automatically.

In WSL bash:

```bash
uv run python .cursor/scripts/run_tests.py tests/deploy -q
```

From Windows PowerShell (do **not** use `uv run python` — Windows uv breaks the venv):

```bash
wsl -e bash -lc "cd '/mnt/c/Users/codya/Desktop/Projects/laken' && uv run pytest tests/deploy -q"
```

Prefer `uv run pytest` directly in WSL when already in bash.

## Success criteria

- Exit code 0
- On failure: read traceback, fix source under `src/` or `tests/`, re-run — do not patch `.pytest_cache/`

## Do not

- `python -m pytest` or bare `pytest` without `uv run`
- Delete `.pytest_cache/` as a “fix” unless the user asks
