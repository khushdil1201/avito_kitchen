.PHONY: install lint type test check openapi up down logs migrate

install:
	python -m pip install -e ".[dev]"

lint:
	ruff check .

type:
	mypy

test:
	pytest

check: lint type test

openapi:
	python scripts/export_openapi.py

up:
	docker compose up --build --detach

down:
	docker compose down

logs:
	docker compose logs --follow

migrate:
	docker compose run --rm migrate
