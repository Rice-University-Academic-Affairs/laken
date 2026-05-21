import os
import subprocess
import sys


def _run_import_script(tmp_path, *, extra_env: dict[str, str] | None = None) -> str:
    env = {k: v for k, v in os.environ.items() if k != "LAKEN_TEST_VAR"}
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os; import laken; print(os.getenv('LAKEN_TEST_VAR', ''))",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_import_loads_dotenv_from_cwd(tmp_path):
    (tmp_path / ".env").write_text("LAKEN_TEST_VAR=from-dotenv\n")
    assert _run_import_script(tmp_path) == "from-dotenv"


def test_import_does_not_override_existing_env(tmp_path):
    (tmp_path / ".env").write_text("LAKEN_TEST_VAR=from-dotenv\n")
    assert _run_import_script(tmp_path, extra_env={"LAKEN_TEST_VAR": "from-shell"}) == "from-shell"


def test_dotenv_disabled_by_env_var(tmp_path):
    (tmp_path / ".env").write_text("LAKEN_TEST_VAR=from-dotenv\n")
    assert _run_import_script(tmp_path, extra_env={"PYTHON_DOTENV_DISABLED": "1"}) == ""
