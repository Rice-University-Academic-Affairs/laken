---
name: run-lint
description: Lint laken Python sources with Ruff via uv. Use for style checks, import order, and before committing changes.
---

# Run lint

## When to use

- After editing Python under `src/` or `tests/`
- User asks for lint / style check
- Pair with tests before finishing a task

## Prerequisites

- Repo root as cwd
- Dev env synced; run `sync-dev-env` first if this is the first use, dependencies changed, or Ruff is missing
- Bash on Linux, Cursor Cloud, or WSL (see AGENTS.md)

## Steps

Check:

```bash
uv run ruff check
```

Auto-format when the user wants formatting fixes applied:

```bash
uv run ruff format
```

Re-run `uv run ruff check` after format if needed.

## Success criteria

- `uv run ruff check` exits 0
- Fix reported issues in source files; do not edit `.ruff_cache/`

## Do not

- Run `ruff` globally without `uv run`
- Disable or weaken Ruff rules in `pyproject.toml` unless the user asks
