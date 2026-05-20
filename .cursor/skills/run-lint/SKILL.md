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

- Repo root as cwd in **WSL bash** (on Windows: `/mnt/c/.../laken`, not PowerShell)
- Dev env synced: `uv sync` in WSL (run first if unsure)

## Steps

1. Ensure dependencies are installed:

```bash
uv sync
```

2. Check (required):

```bash
uv run ruff check
```

3. Auto-format (optional, when user wants fixes applied):

```bash
uv run ruff format
```

Re-run `uv run ruff check` after format if needed.

### Optional script (WSL on Windows)

From repo root. On Windows hosts, `.cursor/scripts/run_lint.py` runs `uv` inside WSL automatically.

In WSL bash:

```bash
uv run python .cursor/scripts/run_lint.py
```

From Windows PowerShell:

```bash
wsl -e bash -lc "cd '/mnt/c/Users/codya/Desktop/Projects/laken' && uv run ruff check"
```

Prefer `uv run ruff` directly in WSL when already in bash.

## Success criteria

- `uv run ruff check` exits 0
- Fix reported issues in source files; do not edit `.ruff_cache/`

## Do not

- Run `ruff` globally without `uv run`
- Disable or weaken Ruff rules in `pyproject.toml` unless the user asks
