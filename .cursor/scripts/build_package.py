import sys

from _uv import run_uv


def main(argv: list[str]) -> int:
    return run_uv(["build", *argv])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
