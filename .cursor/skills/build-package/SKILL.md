---
name: build-package
description: Build the laken wheel and sdist with uv build. Use when validating packaging, hatchling config, or dist/ output.
---

# Build package

## When to use

- Verifying `pyproject.toml` / hatchling build config
- User asks to build a wheel locally
- Checking what lands in `dist/` (not required for routine test/lint work)

## Prerequisites

- Repo root as cwd
- Dev env synced; run `sync-dev-env` first if this is the first use, dependencies changed, or build tooling is missing
- Linux/Cursor Cloud: use the native shell; Windows hosts: use WSL bash

## Steps

Run:

```bash
uv build
```

Inspect output under `dist/` (e.g. `laken-*.whl`). Do not commit `dist/` — it is gitignored.

## Success criteria

- `uv build` exits 0
- At least one `.whl` in `dist/` matching project name `laken`

## Do not

- Hand-edit files in `dist/` or `build/`
- Commit `dist/` artifacts to git
