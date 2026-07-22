"""Seed the local database with deterministic synthetic records."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database.seed import seed_demo_data  # noqa: E402
from app.database.session import create_schema, session_scope  # noqa: E402


def main() -> None:
    create_schema()
    with session_scope() as session:
        business = seed_demo_data(session)
        print(f"Demo data ready for {business.name} (business id {business.id}).")


if __name__ == "__main__":
    main()
