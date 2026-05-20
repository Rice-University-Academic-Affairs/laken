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
- `uv sync` completed at least once

## Steps

1. From repo root:

```bash
uv sync
uv build
```

2. Inspect output under `dist/` (e.g. `laken-*.whl`). Do not commit `dist/` — it is gitignored.

## Success criteria

- `uv build` exits 0
- At least one `.whl` in `dist/` matching project name `laken`

## Do not

- Hand-edit files in `dist/` or `build/`
- Commit `dist/` artifacts to git
