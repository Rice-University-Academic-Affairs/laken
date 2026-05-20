---
name: sync-dev-env
description: Install or refresh the laken dev environment with uv sync. Use when setting up the repo, after dependency changes, or when pytest/ruff are missing.
---

# Sync dev environment

## When to use

- First time working in this repository
- `pyproject.toml` or `uv.lock` changed
- `uv run pytest` or `uv run ruff` fails because tools are not installed

## Prerequisites

- [uv](https://docs.astral.sh/uv/) installed on `PATH`
- Shell at repo root (`pyproject.toml`, `uv.lock` present)
- Cursor Cloud and Linux CI: use the native Linux shell, usually `/workspace`
- Windows hosts: use WSL bash, e.g. `/mnt/c/Users/.../laken`; do not run Windows `uv` from PowerShell or cmd

## Steps

1. From repo root:

```bash
uv sync
```

2. Wait for completion. First sync may take a while (includes `pyspark` and other heavy deps).

3. Confirm `.venv` has `bin/` and `lib/` (Unix layout), not `Scripts/` + `Lib/`.

## If `uv sync` fails

Stop. **Do not** delete `.venv` unless the user explicitly asks.

On Windows hosts, `failed to remove file .venv\lib64` or mixed `Lib`/`lib64` usually means native Windows `uv` ran on `C:\...` and conflicted with the WSL venv. Tell the user; they can recreate from WSL only if they explicitly choose to: `rm -rf .venv && uv sync` in bash.

## Success criteria

- Exit code 0
- `.venv/` exists at repo root
- `uv run pytest --version` and `uv run ruff --version` succeed

## Do not

- Delete or recreate `.venv` unless the user explicitly asks in the current message
- `pip install -e .` or `pip install pytest ruff` unless the user explicitly asks
- Edit files inside `.venv/`
- Commit `.venv/` (gitignored)
