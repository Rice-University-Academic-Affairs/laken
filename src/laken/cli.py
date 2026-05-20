import json
import subprocess

import requests
import typer

import laken.deploy  # noqa: F401
from laken.deploy.build import run_build
from laken.deploy.config import load_deploy_config, require_project_root
from laken.deploy.fabric_client import publish_wheel
from laken.deploy.project import read_project_metadata
from laken.deploy.wheel import resolve_wheel

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.callback()
def main() -> None:
    pass


@app.command()
def deploy(
    workspace_id: str | None = typer.Option(None, "--workspace-id"),
    environment_id: str | None = typer.Option(None, "--environment-id"),
) -> None:
    _exit_on_error(lambda: _deploy_project(workspace_id, environment_id))


def _deploy_project(
    workspace_id: str | None = None,
    environment_id: str | None = None,
) -> None:
    require_project_root()
    metadata = read_project_metadata()
    config = load_deploy_config(workspace_id, environment_id)
    try:
        run_build()
    except subprocess.CalledProcessError as exc:
        raise typer.Exit(exc.returncode or 1) from exc
    wheel_path, wheel_version = resolve_wheel(metadata.name)
    typer.echo(f"Built wheel: {wheel_path}")
    publish_wheel(config=config, wheel_path=wheel_path)
    typer.echo(
        f"{metadata.name} {wheel_version} -> workspace {config.workspace_id} "
        f"environment {config.environment_id}"
    )


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
