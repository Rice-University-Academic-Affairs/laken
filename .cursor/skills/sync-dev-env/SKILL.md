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
- Repo root as cwd (`pyproject.toml`, `uv.lock` present)
- Linux/Cursor Cloud: use the native shell; Windows hosts: use WSL bash
- Never delete or recreate `.venv` unless the user explicitly asks

## Steps

Run:

```bash
uv sync
```

First sync may take a while because the dev environment includes heavy dependencies.

## If `uv sync` fails

Stop and report the error. On Windows hosts, `failed to remove file .venv\lib64` or mixed `Lib`/`lib64` usually means native Windows `uv` touched a WSL repo.

## Success criteria

- Exit code 0
- `.venv/` exists with Unix layout (`bin/`, `lib/`)
- `uv run pytest --version` and `uv run ruff --version` succeed

## Do not

- Delete or recreate `.venv` unless the user explicitly asks
- Use `pip install -e .` or install dev tools with pip unless the user explicitly asks
- Edit files inside `.venv/`
