import pytest

from laken.deploy.project import read_project_metadata


def test_reads_project_metadata(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname = 'my-app'\nversion = '1.2.3'\n")

    metadata = read_project_metadata(pyproject)

    assert metadata.name == "my-app"
    assert metadata.version == "1.2.3"


def test_dynamic_version_has_no_pin(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "[project]\nname = 'my-app'\ndynamic = ['version']\n"
    )

    metadata = read_project_metadata(pyproject)

    assert metadata.name == "my-app"
    assert metadata.version == ""
    assert metadata.wheel_version_pin() is None


def test_requires_project_name(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nversion = '1.2.3'\n")

    with pytest.raises(ValueError, match=r"\[project\]\.name"):
        read_project_metadata(pyproject)
