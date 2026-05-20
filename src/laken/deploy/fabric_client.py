import time
from pathlib import Path
from typing import Any

import requests
import typer

from laken.deploy.config import DeployConfig

BASE_URL = "https://api.fabric.microsoft.com/v1"
POLL_TIMEOUT_SECONDS = 1800
REQUEST_TIMEOUT_SECONDS = 60
POLL_INTERVAL_SECONDS = 5

_SUCCESS_STATUSES = {"succeeded", "completed", "success"}
_FAILURE_STATUSES = {"failed", "cancelled", "canceled"}


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
        typer.echo("Upload accepted.")

        response = requests.post(
            f"{environment_url}/staging/publish?beta=false",
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        _raise_for_status(response)

        operation_id = response.headers.get("x-ms-operation-id")
        if operation_id:
            self._poll_operation(token, operation_id)
        else:
            self._poll_publish_details(token)
        typer.echo("Publish succeeded.")

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
        return response.json()["access_token"]

    def _environment_url(self) -> str:
        return (
            f"{BASE_URL}/workspaces/{self.config.workspace_id}"
            f"/environments/{self.config.environment_id}"
        )

    def _auth_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def _poll_operation(self, token: str, operation_id: str) -> None:
        url = f"{BASE_URL}/operations/{operation_id}"

        def get_status() -> str | None:
            response = requests.get(
                url,
                headers=self._auth_headers(token),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            _raise_for_status(response)
            return _extract_status(response.json())

        _poll_until_terminal(get_status)

    def _poll_publish_details(self, token: str) -> None:
        url = f"{self._environment_url()}/staging/publishDetails"

        def get_status() -> str | None:
            response = requests.get(
                url,
                headers=self._auth_headers(token),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            _raise_for_status(response)
            return _extract_status(response.json())

        _poll_until_terminal(get_status)


def _poll_until_terminal(get_status) -> None:
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        status = get_status()
        normalized = status.lower() if status else None
        if normalized in _SUCCESS_STATUSES:
            return
        if normalized in _FAILURE_STATUSES:
            raise RuntimeError(f"Fabric publish {status}")
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError("Fabric publish timed out")


def _extract_status(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("status", "state"):
        value = payload.get(key)
        if value:
            return str(value)
    details = payload.get("publishDetails")
    if isinstance(details, dict):
        return _extract_status(details)
    if isinstance(details, list):
        for item in reversed(details):
            status = _extract_status(item)
            if status:
                return status
    return None


def _raise_for_status(response: requests.Response) -> None:
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        url = response.url or getattr(response.request, "url", "")
        message = f"HTTP {response.status_code} for {url}: {response.text}"
        raise RuntimeError(message) from exc
