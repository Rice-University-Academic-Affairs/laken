import sys

from _uv import run_uv


def main(argv: list[str]) -> int:
    args = list(argv)
    if "--format" in args:
        args.remove("--format")
        return run_uv(["run", "ruff", "format", *args])
    return run_uv(["run", "ruff", "check", *args])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
