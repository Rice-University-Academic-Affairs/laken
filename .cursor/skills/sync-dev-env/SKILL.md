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

- [uv](https://docs.astral.sh/uv/) installed in **WSL**
- Shell: **WSL bash** at repo root (`pyproject.toml`, `uv.lock` present), e.g. `/mnt/c/Users/.../laken`
- On a Windows host: do **not** run this skill from PowerShell — use WSL or `wsl -e bash -lc 'cd /mnt/c/.../laken && uv sync'`

## Steps

1. From repo root in WSL:

```bash
uv sync
```

2. Wait for completion. First sync may take a while (includes `pyspark` and other heavy deps).

3. Confirm `.venv` has `bin/` and `lib/` (Unix layout), not `Scripts/` + `Lib/`.

## If `uv sync` fails

Stop. **Do not** delete `.venv` unless the user explicitly asks.

`failed to remove file .venv\lib64` or mixed `Lib`/`lib64` usually means **native Windows `uv`** ran on `C:\...` and conflicted with the WSL venv. Tell the user; they should recreate from WSL only: `rm -rf .venv && uv sync` in bash.

## Success criteria

- Exit code 0
- `.venv/` exists at repo root
- `uv run pytest --version` and `uv run ruff --version` succeed

## Do not

- Delete or recreate `.venv` unless the user explicitly asks in the current message
- `pip install -e .` or `pip install pytest ruff` unless the user explicitly asks
- Edit files inside `.venv/`
- Commit `.venv/` (gitignored)
