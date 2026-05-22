import json
import subprocess
from pathlib import Path

import requests
import typer

from laken._env import load_environment
from laken.deploy.build import run_build
from laken.deploy.config import load_deploy_config, require_project_root
from laken.deploy.fabric_client import publish_wheel
from laken.deploy.project import ProjectMetadata, read_project_metadata
from laken.deploy.wheel import resolve_wheel
from laken.local_lakehouse import LocalLakehouse

load_environment()

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
def deploy(
    workspace_id: str | None = typer.Option(None, "--workspace-id"),
    environment_id: str | None = typer.Option(None, "--environment-id"),
) -> None:
    def run() -> None:
        _build_project()
        _upload_project(workspace_id, environment_id)

    _exit_on_error(run)


@app.command()
def status() -> None:
    def run() -> None:
        rows = LocalLakehouse().status()
        _print_status(rows)

    _exit_on_error(run)


@app.command()
def refresh(table: str) -> None:
    def run() -> None:
        LocalLakehouse().refresh_table(table)

    _exit_on_error(run)


@app.command()
def reset(table: str) -> None:
    def run() -> None:
        LocalLakehouse().reset_table(table)

    _exit_on_error(run)


def _exit_on_error(action) -> None:
    try:
        action()
    except typer.BadParameter:
        raise
    except typer.Exit:
        raise
    except (
        FileNotFoundError,
        RuntimeError,
        TimeoutError,
        ValueError,
        requests.RequestException,
        KeyError,
        json.JSONDecodeError,
    ) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


def _print_status(rows: list[dict[str, str]]) -> None:
    headers = ["Table", "State", "Source version", "Notes"]
    values = [[row["table"], row["state"], row["source_version"], row["notes"]] for row in rows]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in values))
        if values
        else len(headers[index])
        for index in range(len(headers))
    ]
    typer.echo(" ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    for row in values:
        typer.echo(" ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def _build_project() -> tuple[ProjectMetadata, Path]:
    require_project_root()
    metadata = read_project_metadata()
    try:
        run_build()
    except subprocess.CalledProcessError as exc:
        raise typer.Exit(exc.returncode or 1) from exc
    wheel_path, _ = resolve_wheel(metadata.name, metadata.wheel_version_pin())
    typer.echo(f"Built wheel: {wheel_path}")
    return metadata, wheel_path


def _upload_project(
    workspace_id: str | None = None,
    environment_id: str | None = None,
) -> None:
    require_project_root()
    config = load_deploy_config(workspace_id, environment_id)
    metadata = read_project_metadata()
    wheel_path, wheel_version = resolve_wheel(metadata.name, metadata.wheel_version_pin())
    typer.echo(f"Wheel found: {wheel_path}")
    publish_wheel(config=config, wheel_path=wheel_path)
    typer.echo(
        f"{metadata.name} {wheel_version} -> workspace {config.workspace_id} "
        f"environment {config.environment_id}"
    )

