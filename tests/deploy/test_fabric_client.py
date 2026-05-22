from unittest.mock import Mock

import pytest
import requests

from laken.deploy.config import DeployConfig
from laken.deploy.fabric_client import BASE_URL, FabricEnvironmentPublisher, publish_wheel


def _config():
    return DeployConfig(
        tenant_id="tenant",
        client_id="client",
        client_secret="secret",
        workspace_id="workspace",
        environment_id="environment",
    )


def _response(json_data=None, headers=None, url="https://example.test", status_code=200):
    response = Mock(spec=requests.Response)
    response.headers = headers or {}
    response.status_code = status_code
    response.text = ""
    response.url = url
    response.raise_for_status.return_value = None
    response.json.return_value = json_data or {}
    return response


def test_publish_wheel_accepts_http_200_and_202(monkeypatch, tmp_path, capsys):
    wheel = tmp_path / "app-1.0.0-py3-none-any.whl"
    wheel.write_bytes(b"wheel")
    post = Mock(
        side_effect=[
            _response({"access_token": "token"}),
            _response(status_code=200),
            _response(status_code=202),
        ]
    )
    get = Mock()
    monkeypatch.setattr("laken.deploy.fabric_client.requests.post", post)
    monkeypatch.setattr("laken.deploy.fabric_client.requests.get", get)

    publish_wheel(config=_config(), wheel_path=wheel)

    token_call, upload_call, publish_call = post.call_args_list
    assert token_call.args[0] == ("https://login.microsoftonline.com/tenant/oauth2/v2.0/token")
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
    get.assert_not_called()
    output = capsys.readouterr().out
    assert "Wheel upload accepted (HTTP 200)." in output
    assert "Submitting Fabric Environment publish..." in output
    assert "Publish request accepted (HTTP 202)." in output


def test_token_missing_access_token_raises(monkeypatch):
    monkeypatch.setattr(
        "laken.deploy.fabric_client.requests.post",
        Mock(return_value=_response({})),
    )
    publisher = FabricEnvironmentPublisher(_config())
    with pytest.raises(RuntimeError, match="missing access_token"):
        publisher._token()
