from unittest.mock import Mock

import requests

from laken.deploy.config import DeployConfig
from laken.deploy.fabric_client import BASE_URL, publish_wheel


def _config():
    return DeployConfig(
        tenant_id="tenant",
        client_id="client",
        client_secret="secret",
        workspace_id="workspace",
        environment_id="environment",
    )


def _response(json_data=None, headers=None, url="https://example.test"):
    response = Mock(spec=requests.Response)
    response.headers = headers or {}
    response.status_code = 200
    response.text = ""
    response.url = url
    response.raise_for_status.return_value = None
    response.json.return_value = json_data or {}
    return response


def test_publish_wheel_uses_operation_poll(monkeypatch, tmp_path, capsys):
    wheel = tmp_path / "app-1.0.0-py3-none-any.whl"
    wheel.write_bytes(b"wheel")
    post = Mock(
        side_effect=[
            _response({"access_token": "token"}),
            _response(),
            _response(headers={"x-ms-operation-id": "operation"}),
        ]
    )
    get = Mock(return_value=_response({"status": "Succeeded"}))
    monkeypatch.setattr("laken.deploy.fabric_client.requests.post", post)
    monkeypatch.setattr("laken.deploy.fabric_client.requests.get", get)

    publish_wheel(config=_config(), wheel_path=wheel)

    token_call, upload_call, publish_call = post.call_args_list
    assert token_call.args[0] == (
        "https://login.microsoftonline.com/tenant/oauth2/v2.0/token"
    )
    assert token_call.kwargs["data"]["scope"] == "https://api.fabric.microsoft.com/.default"
    assert upload_call.args[0] == (
        f"{BASE_URL}/workspaces/workspace/environments/environment"
        "/staging/libraries/app-1.0.0-py3-none-any.whl"
    )
    assert upload_call.kwargs["headers"]["Authorization"] == "Bearer token"
    assert upload_call.kwargs["headers"]["Content-Type"] == "application/octet-stream"
    assert publish_call.args[0] == (
        f"{BASE_URL}/workspaces/workspace/environments/environment/staging/publish?beta=false"
    )
    get.assert_called_once_with(
        f"{BASE_URL}/operations/operation",
        headers={"Authorization": "Bearer token"},
        timeout=60,
    )
    assert "Publish succeeded." in capsys.readouterr().out


def test_publish_wheel_falls_back_to_publish_details(monkeypatch, tmp_path):
    wheel = tmp_path / "app-1.0.0-py3-none-any.whl"
    wheel.write_bytes(b"wheel")
    post = Mock(
        side_effect=[
            _response({"access_token": "token"}),
            _response(),
            _response(),
        ]
    )
    get = Mock(return_value=_response({"publishDetails": {"status": "Succeeded"}}))
    monkeypatch.setattr("laken.deploy.fabric_client.requests.post", post)
    monkeypatch.setattr("laken.deploy.fabric_client.requests.get", get)

    publish_wheel(config=_config(), wheel_path=wheel)

    get.assert_called_once_with(
        f"{BASE_URL}/workspaces/workspace/environments/environment/staging/publishDetails",
        headers={"Authorization": "Bearer token"},
        timeout=60,
    )
