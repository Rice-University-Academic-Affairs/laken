import json
import subprocess

import requests
import typer

from laken._env import load_environment
from laken.deploy.build import build_wheel
from laken.deploy.config import load_deploy_config, require_project_root
from laken.deploy.fabric_client import publish_wheel
from laken.deploy.project import read_project_metadata
from laken.local_lakehouse import refresh_table

load_environment()

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
def deploy(
    workspace_id: str | None = typer.Option(None, "--workspace-id"),
    environment_id: str | None = typer.Option(None, "--environment-id"),
) -> None:
    def run() -> None:
        require_project_root()
        metadata = read_project_metadata()
        config = load_deploy_config(workspace_id, environment_id)
        try:
            wheel_path, wheel_version = build_wheel(metadata.name)
        except subprocess.CalledProcessError as exc:
            raise typer.Exit(exc.returncode or 1) from exc
        typer.echo(f"Built {wheel_path.name}")
        publish_wheel(config=config, wheel_path=wheel_path)
        typer.echo(
            f"{metadata.name} {wheel_version} -> workspace {config.workspace_id} "
            f"environment {config.environment_id}"
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
