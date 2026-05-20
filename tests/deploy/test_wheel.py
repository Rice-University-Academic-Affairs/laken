import pytest

from laken.deploy.wheel import resolve_wheel


def test_resolves_matching_wheel(monkeypatch, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    expected = dist / "my_app-0.2.0-py3-none-any.whl"
    (dist / "my_app-0.1.0-py3-none-any.whl").write_text("")
    expected.write_text("")
    monkeypatch.chdir(tmp_path)

    assert resolve_wheel("my-app") == expected


def test_missing_dist_raises(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError, match="dist/"):
        resolve_wheel("my-app")


def test_no_matching_wheel_raises(monkeypatch, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "other-0.1.0-py3-none-any.whl").write_text("")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError, match="my-app"):
        resolve_wheel("my-app")


def test_multiple_same_version_wheels_raise(monkeypatch, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "my_app-0.1.0-py3-none-any.whl").write_text("")
    (dist / "my_app-0.1.0-cp311-cp311-linux_x86_64.whl").write_text("")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RuntimeError, match="Multiple wheels"):
        resolve_wheel("my-app")
