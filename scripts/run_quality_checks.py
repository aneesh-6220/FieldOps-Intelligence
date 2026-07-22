"""Run the same quality gates used by CI."""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    for command in (["ruff", "check", "."], ["mypy", "app", "scripts"], ["pytest"]):
        print(f"Running: {' '.join(command)}")
        subprocess.run(command, check=True, cwd=PROJECT_ROOT)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
