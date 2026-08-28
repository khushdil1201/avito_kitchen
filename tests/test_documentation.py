import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIRECTORY = PROJECT_ROOT / "docs"
DIAGRAMS = (
    "c4.puml",
    "cjm-user.puml",
    "cjm-restaurant.puml",
    "database.puml",
)


@pytest.mark.parametrize("filename", DIAGRAMS)
def test_plantuml_source_is_self_contained(filename: str) -> None:
    source = (DOCS_DIRECTORY / filename).read_text(encoding="utf-8")
    meaningful_lines = [line.strip() for line in source.splitlines() if line.strip()]

    assert meaningful_lines[0].startswith("@startuml")
    assert meaningful_lines[-1] == "@enduml"
    assert source.count("@startuml") == 1
    assert source.count("@enduml") == 1
    assert "includeurl" not in source.lower()


def test_database_diagram_contains_every_migrated_table() -> None:
    migration = (PROJECT_ROOT / "migrations" / "001_initial_schema.sql").read_text(encoding="utf-8")
    diagram = (DOCS_DIRECTORY / "database.puml").read_text(encoding="utf-8")

    migrated_tables = set(re.findall(r"CREATE TABLE ([a-z_]+)", migration))
    documented_tables = set(re.findall(r"^entity ([a-z_]+)", diagram, flags=re.MULTILINE))

    assert documented_tables == migrated_tables


def test_c4_preserves_service_and_database_boundaries() -> None:
    diagram = (DOCS_DIRECTORY / "c4.puml").read_text(encoding="utf-8")

    assert "restaurant_api --> kitchen_api" in diagram
    assert "kitchen_api --> restaurant_api" not in diagram
    assert "kitchen_api --> postgres" in diagram
    assert "restaurant_api --> postgres" not in diagram


def test_customer_journeys_cover_implemented_order_outcomes() -> None:
    user_journey = (DOCS_DIRECTORY / "cjm-user.puml").read_text(encoding="utf-8")
    restaurant_journey = (DOCS_DIRECTORY / "cjm-restaurant.puml").read_text(encoding="utf-8")

    assert "Idempotency-Key" in user_journey
    assert "ready" in user_journey
    assert "rejected" in user_journey
    assert "created → accepted" in restaurant_journey
    assert "created → rejected" in restaurant_journey
    assert "accepted → preparing" in restaurant_journey
    assert "preparing → ready" in restaurant_journey


def test_readme_covers_acceptance_topics_and_has_valid_local_links() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    required_sections = {
        "## Быстрый запуск",
        "## Сквозной демонстрационный сценарий",
        "## Архитектура",
        "## Ключевые технические решения",
        "## Осознанные упрощения MVP",
        "## Путь масштабирования",
        "## Матрица критериев приёмки",
    }

    assert required_sections.issubset(set(readme.splitlines()))

    local_links = re.findall(r"\[[^]]+]\((?!https?://)([^)]+)\)", readme)
    assert local_links
    for link in local_links:
        assert (PROJECT_ROOT / link).exists(), f"Локальная ссылка отсутствует: {link}"
