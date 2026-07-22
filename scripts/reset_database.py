"""Explicitly clear and reseed only the dedicated demo database."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database.seed import clear_demo_database, seed_demo_data  # noqa: E402
from app.database.session import WorkspaceMode, create_schema, session_scope  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reset synthetic data in the separate FieldOps demo database"
    )
    parser.add_argument("--yes", action="store_true", help="Confirm deletion without prompting")
    args = parser.parse_args()
    if not args.yes and input("Delete and reseed the demo database only? [y/N] ").lower() != "y":
        print("Reset cancelled.")
        return
    create_schema(workspace=WorkspaceMode.DEMO)
    with session_scope(workspace=WorkspaceMode.DEMO) as session:
        clear_demo_database(session)
        seed_demo_data(session)
    print("Demo database reset. The operational database was not modified.")


if __name__ == "__main__":
    main()
