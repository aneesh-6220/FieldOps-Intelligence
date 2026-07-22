"""Explicitly clear and reseed the configured local database."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database.seed import clear_database, seed_demo_data  # noqa: E402
from app.database.session import create_schema, session_scope  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset FieldOps synthetic demo data")
    parser.add_argument("--yes", action="store_true", help="Confirm deletion without prompting")
    args = parser.parse_args()
    if (
        not args.yes
        and input("Delete all configured FieldOps data and reseed? [y/N] ").lower() != "y"
    ):
        print("Reset cancelled.")
        return
    create_schema()
    with session_scope() as session:
        clear_database(session)
        seed_demo_data(session)
    print("Database reset with synthetic demo data.")


if __name__ == "__main__":
    main()
