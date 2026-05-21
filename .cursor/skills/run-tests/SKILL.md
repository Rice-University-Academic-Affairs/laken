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
- Bash on Linux, Cursor Cloud, or WSL (see AGENTS.md)

## Steps

**Full suite (required after any `src/` or `tests/` change):**

```bash
uv run pytest
```

This runs unit tests and `integration`-marked tests. Do not use `-m "not integration"` unless the user explicitly asks for unit tests only.

Integration tests need `AZURE_*` and `FABRIC_*` env vars (see AGENTS.md). They skip when credentials are absent; when present, they must run and pass (or failures must be reported).

**Unit tests only** (only when the user asks):

```bash
uv run pytest -m "not integration"
```

## Success criteria

- Exit code 0
- Integration tests executed when Fabric credentials are configured (not silently omitted from the run)
- On failure: read traceback, fix source under `src/` or `tests/`, re-run — do not patch `.pytest_cache/`

## Do not

- `python -m pytest` or bare `pytest` without `uv run`
- Skip integration tests by default when verifying a change
- Delete `.pytest_cache/` as a “fix” unless the user asks
