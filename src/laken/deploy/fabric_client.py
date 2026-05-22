from pathlib import Path

import requests
import typer

from laken.deploy.config import DeployConfig

BASE_URL = "https://api.fabric.microsoft.com/v1"
REQUEST_TIMEOUT_SECONDS = 60


def publish_wheel(*, config: DeployConfig, wheel_path: Path) -> None:
    publisher = FabricEnvironmentPublisher(config)
    publisher.publish(wheel_path)


class FabricEnvironmentPublisher:
    def __init__(self, config: DeployConfig):
        self.config = config

    def publish(self, wheel_path: Path) -> None:
        token = self._token()
        environment_url = self._environment_url()
        headers = self._auth_headers(token)

        typer.echo(f"Uploading {wheel_path.name} to Fabric environment...")
        with wheel_path.open("rb") as wheel_file:
            response = requests.post(
                f"{environment_url}/staging/libraries/{wheel_path.name}",
                headers={**headers, "Content-Type": "application/octet-stream"},
                data=wheel_file,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        _raise_for_status(response)
        typer.echo(f"Wheel upload accepted (HTTP {response.status_code}).")

        typer.echo("Submitting Fabric Environment publish...")
        response = requests.post(
            f"{environment_url}/staging/publish?beta=false",
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        _raise_for_status(response)
        typer.echo(
            "Publish submitted. Fabric rebuilds the Environment asynchronously; "
            "notebooks can import after the Environment publish completes."
        )

    def _token(self) -> str:
        response = requests.post(
            f"https://login.microsoftonline.com/{self.config.tenant_id}/oauth2/v2.0/token",
            data={
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "grant_type": "client_credentials",
                "scope": "https://api.fabric.microsoft.com/.default",
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        _raise_for_status(response)
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise RuntimeError("OAuth response missing access_token")
        return token

    def _environment_url(self) -> str:
        return (
            f"{BASE_URL}/workspaces/{self.config.workspace_id}"
            f"/environments/{self.config.environment_id}"
        )

    def _auth_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}


def _raise_for_status(response: requests.Response) -> None:
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        url = response.url or getattr(response.request, "url", "")
        message = f"HTTP {response.status_code} for {url}: {response.text}"
        raise RuntimeError(message) from exc
