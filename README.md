# Avito Kitchen

Avito Kitchen is an MVP food-ordering platform. It exposes an API for the web
client and an integration API for partner restaurants. A separate restaurant
service in this repository demonstrates that integration end to end.

## MVP scope

The first version supports the complete ordering path:

1. A customer browses available restaurants and their menus.
2. The customer creates an order from one restaurant.
3. The platform validates current product availability and snapshots prices.
4. The restaurant accepts or rejects the order through the integration API.
5. The customer observes subsequent order status changes.

Authentication, payment processing, courier logistics, promotions, ratings,
and full-text or geo search are intentionally outside the two-day MVP. Their
extension points and production trade-offs will be documented as the system is
built.

## Planned architecture

- **Platform API:** Python, FastAPI, Pydantic, and `asyncpg` with explicit SQL.
- **Restaurant service:** a separate FastAPI application acting as one partner.
- **Database:** PostgreSQL with versioned SQL migrations.
- **Integration:** synchronous HTTP for commands and idempotent callbacks for
  restaurant status updates.
- **Runtime:** Docker Compose.
- **Quality:** Ruff, mypy, pytest, and HTTP integration tests.
- **Documentation:** generated OpenAPI plus Mermaid source for C4, ER, and CJM
  diagrams.

Detailed design decisions and local launch instructions will be added alongside
the relevant implementation so the documentation remains executable and
consistent with the code.

## Delivery plan

See [docs/PLAN.md](docs/PLAN.md) for the staged implementation plan and the AI
working prompt required by the assignment.

