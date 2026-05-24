import json
import subprocess
from pathlib import Path

import requests
import typer
from packaging.utils import parse_wheel_filename
from packaging.version import Version

from laken._env import load_environment
from laken.deploy.build import run_build
from laken.deploy.config import load_deploy_config, require_project_root
from laken.deploy.fabric_client import publish_wheel
from laken.deploy.project import ProjectMetadata, read_project_metadata
from laken.deploy.wheel import wheel_from_build
from laken.local_lakehouse import refresh_table

load_environment()

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
def deploy(
    workspace_id: str | None = typer.Option(None, "--workspace-id"),
    environment_id: str | None = typer.Option(None, "--environment-id"),
) -> None:
    def run() -> None:
        _, wheel_path, wheel_version = _build_project()
        _upload_project(
            workspace_id,
            environment_id,
            wheel_path=wheel_path,
            wheel_version=wheel_version,
        )

    _exit_on_error(run)


@app.command()
def refresh(table: str) -> None:
    def run() -> None:
        refresh_table(table)

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


def _build_project() -> tuple[ProjectMetadata, Path, Version]:
    require_project_root()
    metadata = read_project_metadata()
    try:
        run_build(metadata.name)
    except subprocess.CalledProcessError as exc:
        raise typer.Exit(exc.returncode or 1) from exc
    wheel_path, wheel_version = wheel_from_build(metadata.name)
    typer.echo(f"Built wheel: {wheel_path}")
    return metadata, wheel_path, wheel_version


def _upload_project(
    workspace_id: str | None = None,
    environment_id: str | None = None,
    *,
    wheel_path: Path | None = None,
    wheel_version: Version | None = None,
) -> None:
    require_project_root()
    config = load_deploy_config(workspace_id, environment_id)
    metadata = read_project_metadata()
    if wheel_path is None:
        wheel_path, wheel_version = wheel_from_build(metadata.name)
    elif wheel_version is None:
        _, parsed_version, _, _ = parse_wheel_filename(wheel_path.name)
        wheel_version = (
            parsed_version if isinstance(parsed_version, Version) else Version(str(parsed_version))
        )
    typer.echo(f"Wheel found: {wheel_path}")
    publish_wheel(config=config, wheel_path=wheel_path)
    typer.echo(
        f"{metadata.name} {wheel_version} -> workspace {config.workspace_id} "
        f"environment {config.environment_id}"
    )
