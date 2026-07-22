.PHONY: install migrate seed run test lint format typecheck quality reset

install:
	python -m pip install -e ".[dev]"

migrate:
	alembic upgrade head

seed:
	python scripts/seed_demo_data.py

run:
	streamlit run app/main.py

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy app scripts

quality: lint typecheck test

reset:
	python scripts/reset_database.py --yes
