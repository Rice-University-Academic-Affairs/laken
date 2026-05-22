import pytest

from laken.deploy.wheel import wheel_from_build


def test_wheel_from_build_returns_single_wheel(monkeypatch, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    expected = dist / "my_app-0.2.0-py3-none-any.whl"
    expected.write_text("")
    monkeypatch.chdir(tmp_path)

    wheel_path, version = wheel_from_build("my-app")

    assert wheel_path == expected
    assert str(version) == "0.2.0"


def test_wheel_from_build_ignores_other_projects(monkeypatch, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    expected = dist / "my_app-0.1.0-py3-none-any.whl"
    (dist / "other_pkg-9.9.9-py3-none-any.whl").write_text("")
    expected.write_text("")
    monkeypatch.chdir(tmp_path)

    wheel_path, version = wheel_from_build("my-app")

    assert wheel_path == expected
    assert str(version) == "0.1.0"


def test_skips_invalid_wheel_filename(monkeypatch, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    expected = dist / "my_app-0.1.0-py3-none-any.whl"
    (dist / "not-a-wheel.txt").write_text("")
    (dist / "broken.whl").write_text("")
    expected.write_text("")
    monkeypatch.chdir(tmp_path)

    wheel_path, _ = wheel_from_build("my-app")
    assert wheel_path == expected


def test_missing_dist_raises(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError, match="dist/"):
        wheel_from_build("my-app")


def test_no_matching_wheel_raises(monkeypatch, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "other-0.1.0-py3-none-any.whl").write_text("")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError, match="my-app"):
        wheel_from_build("my-app")


def test_multiple_project_wheels_raise(monkeypatch, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "my_app-0.1.0-py3-none-any.whl").write_text("")
    (dist / "my_app-0.2.0-py3-none-any.whl").write_text("")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RuntimeError, match="Multiple wheels"):
        wheel_from_build("my-app")
