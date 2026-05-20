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
- Cursor Cloud and Linux CI: use native Linux shell
- Windows hosts: use WSL bash for direct `uv` commands, not PowerShell

## Steps

1. From repo root:

```bash
uv sync
uv build
```

2. Inspect output under `dist/` (e.g. `laken-*.whl`). Do not commit `dist/` — it is gitignored.

### Optional script

From repo root. The direct `uv build` command above is preferred on Linux, Cursor Cloud, macOS, and WSL. `.cursor/scripts/build_package.py` is a small Python wrapper that resolves the repo root; when launched with Windows Python, it runs `uv` inside WSL automatically.

Linux / WSL:

```bash
uv run python .cursor/scripts/build_package.py
```

Windows PowerShell:

```powershell
python .cursor\scripts\build_package.py
```

Do not prefix the wrapper with Windows `uv`.

## Success criteria

- `uv build` exits 0
- At least one `.whl` in `dist/` matching project name `laken`

## Do not

- Hand-edit files in `dist/` or `build/`
- Commit `dist/` artifacts to git
