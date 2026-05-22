import os
import subprocess
import sys


def _run_script(tmp_path, script: str, *, extra_env: dict[str, str] | None = None) -> str:
    env = {k: v for k, v in os.environ.items() if k != "LAKEN_TEST_VAR"}
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_import_does_not_load_dotenv(tmp_path):
    (tmp_path / ".env").write_text("LAKEN_TEST_VAR=from-dotenv\n")
    script = "import os; import laken; print(os.getenv('LAKEN_TEST_VAR', ''))"
    assert _run_script(tmp_path, script) == ""


def test_lakehouse_loads_dotenv_from_cwd(tmp_path):
    (tmp_path / ".env").write_text("LAKEN_TEST_VAR=from-dotenv\n")
    script = (
        "import os; from laken import Lakehouse; "
        "Lakehouse(); print(os.getenv('LAKEN_TEST_VAR', ''))"
    )
    assert _run_script(tmp_path, script) == "from-dotenv"


def test_lakehouse_does_not_override_existing_env(tmp_path):
    (tmp_path / ".env").write_text("LAKEN_TEST_VAR=from-dotenv\n")
    script = (
        "import os; from laken import Lakehouse; "
        "Lakehouse(); print(os.getenv('LAKEN_TEST_VAR', ''))"
    )
    assert (
        _run_script(tmp_path, script, extra_env={"LAKEN_TEST_VAR": "from-shell"}) == "from-shell"
    )


def test_load_environment_loads_dotenv_from_cwd(tmp_path):
    (tmp_path / ".env").write_text("LAKEN_TEST_VAR=from-dotenv\n")
    script = (
        "import os; from laken import load_environment; "
        "load_environment(); print(os.getenv('LAKEN_TEST_VAR', ''))"
    )
    assert _run_script(tmp_path, script) == "from-dotenv"


def test_cli_import_loads_dotenv(tmp_path):
    (tmp_path / ".env").write_text("LAKEN_TEST_VAR=from-dotenv\n")
    script = "import os; from laken.cli import app; print(os.getenv('LAKEN_TEST_VAR', ''))"
    assert _run_script(tmp_path, script) == "from-dotenv"
