import pytest
import typer

from laken.deploy.config import load_deploy_config, require_project_root


def test_missing_env_vars_lists_required_names(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'app'\nversion = '1.0.0'\n")
    monkeypatch.chdir(tmp_path)
    for name in [
        "AZURE_TENANT_ID",
        "AZURE_CLIENT_ID",
        "AZURE_CLIENT_SECRET",
        "FABRIC_WORKSPACE_ID",
        "FABRIC_ENVIRONMENT_ID",
    ]:
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(typer.BadParameter) as exc:
        load_deploy_config()

    message = str(exc.value)
    assert "AZURE_TENANT_ID" in message
    assert "AZURE_CLIENT_ID" in message
    assert "AZURE_CLIENT_SECRET" in message
    assert "FABRIC_WORKSPACE_ID" in message
    assert "FABRIC_ENVIRONMENT_ID" in message


def test_fabric_flags_override_env(monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("FABRIC_WORKSPACE_ID", "env-workspace")
    monkeypatch.setenv("FABRIC_ENVIRONMENT_ID", "env-environment")

    config = load_deploy_config("flag-workspace", "flag-environment")

    assert config.tenant_id == "tenant"
    assert config.client_id == "client"
    assert config.client_secret == "secret"
    assert config.workspace_id == "flag-workspace"
    assert config.environment_id == "flag-environment"


def test_require_project_root_exits_without_pyproject(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(typer.Exit) as exc:
        require_project_root()

    assert exc.value.exit_code == 1
