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
- Dev env synced; run `sync-dev-env` first if this is the first use, dependencies changed, or pytest is missing
- Linux/Cursor Cloud: use the native shell; Windows hosts: use WSL bash

## Steps

Pick the narrowest useful scope:

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

## Success criteria

- Exit code 0
- On failure: read traceback, fix source under `src/` or `tests/`, re-run — do not patch `.pytest_cache/`

## Do not

- `python -m pytest` or bare `pytest` without `uv run`
- Delete `.pytest_cache/` as a “fix” unless the user asks
