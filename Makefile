.PHONY: install lint type test check e2e e2e-down openapi up down logs migrate

install:
	python -m pip install -e ".[dev]"

lint:
	ruff check .
	ruff format --check .

type:
	mypy

test:
	pytest

check: lint type test

e2e:
	docker compose -f docker-compose.e2e.yml up --build --detach --wait restaurant-api-e2e
	docker compose -f docker-compose.e2e.yml run --build --rm tests-e2e

e2e-down:
	docker compose -f docker-compose.e2e.yml down --volumes --remove-orphans

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
