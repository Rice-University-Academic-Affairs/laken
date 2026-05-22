import os
from dataclasses import dataclass
from pathlib import Path

import typer


@dataclass(frozen=True)
class DeployConfig:
    tenant_id: str
    client_id: str
    client_secret: str
    workspace_id: str
    environment_id: str


def require_project_root() -> Path:
    pyproject = Path.cwd() / "pyproject.toml"
    if not pyproject.exists():
        typer.echo("Run laken from a project root containing pyproject.toml.", err=True)
        raise typer.Exit(1)
    return pyproject


def load_deploy_config(
    workspace_id: str | None = None,
    environment_id: str | None = None,
) -> DeployConfig:
    values = {
        "AZURE_TENANT_ID": os.getenv("AZURE_TENANT_ID"),
        "AZURE_CLIENT_ID": os.getenv("AZURE_CLIENT_ID"),
        "AZURE_CLIENT_SECRET": os.getenv("AZURE_CLIENT_SECRET"),
        "FABRIC_WORKSPACE_ID": workspace_id or os.getenv("FABRIC_WORKSPACE_ID"),
        "FABRIC_ENVIRONMENT_ID": environment_id or os.getenv("FABRIC_ENVIRONMENT_ID"),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise typer.BadParameter(f"Missing required configuration: {', '.join(missing)}")
    return DeployConfig(
        tenant_id=values["AZURE_TENANT_ID"],
        client_id=values["AZURE_CLIENT_ID"],
        client_secret=values["AZURE_CLIENT_SECRET"],
        workspace_id=values["FABRIC_WORKSPACE_ID"],
        environment_id=values["FABRIC_ENVIRONMENT_ID"],
    )
