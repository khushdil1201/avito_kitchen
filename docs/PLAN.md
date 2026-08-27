# Implementation plan

This document is both the delivery plan and the AI working prompt for the
project. Each stage must be independently reviewable, tested where applicable,
and committed before the next stage starts.

## Engineering principles

- Keep the MVP small but complete: every declared scenario must work end to end.
- Use explicit SQL and transaction boundaries; do not introduce an ORM.
- Keep HTTP, application, and persistence concerns separate.
- Validate state transitions in one place and make externally retried operations
  idempotent.
- Snapshot mutable menu data in orders so order history remains correct.
- Prefer constraints in PostgreSQL for invariants the database can enforce.
- Add infrastructure only when a current scenario requires it; document future
  scaling paths instead of simulating production complexity.

## Stages

1. **Repository foundation** — scope, plan, ignore rules, and Git history.
2. **Application skeleton** — package layout, dependency configuration, health
   endpoint, linting, typing, and a minimal test.
3. **Persistence foundation** — PostgreSQL Compose service, migration runner,
   connection pool, initial relational schema, and ER diagram.
4. **Customer catalogue** — list restaurants, retrieve a menu, filtering and
   pagination, with repository and API tests.
5. **Ordering** — transactional order creation, price snapshots, availability
   checks, idempotency, order lookup, and state-machine tests.
6. **Restaurant integration** — partner API, example restaurant service,
   acceptance/rejection and subsequent status callbacks.
7. **Operational hardening** — structured errors and logs, timeouts, readiness,
   container health checks, and graceful shutdown.
8. **Acceptance documentation** — customer and restaurant CJMs, C4 diagrams,
   OpenAPI export, architecture decisions, limitations, and runbook.
9. **Final verification** — clean Compose build, migrations, automated tests,
   linters, type checks, and manual end-to-end smoke test.

## Two-day target

### Day 1

- Complete stages 1–5.
- Finish the customer ordering path against PostgreSQL.
- Keep unit and integration tests green after each stage.

### Day 2

- Complete stages 6–9.
- Exercise the real cross-service flow through Docker Compose.
- Review documentation against every acceptance criterion.

## Initial domain decisions

- One order contains products from exactly one restaurant.
- A menu item may become unavailable between catalogue viewing and checkout;
  checkout revalidates it and returns a conflict without creating a partial
  order.
- Prices are integer minor units with an ISO currency code; floating-point money
  is forbidden.
- The platform owns the order identifier and state machine. Restaurant-local
  identifiers are stored as external references rather than reused as primary
  keys.
- The client supplies an idempotency key when creating an order. Repeating the
  same request returns the original result; reusing the key for different input
  is rejected.
- No user authentication is implemented per the assignment. A temporary
  `customer_id` carried by requests represents the future identity boundary.

## Definition of done

The repository is complete when a reviewer can clone it, run one documented
Docker Compose command, observe healthy services, execute the documented
customer and restaurant journeys, inspect versioned SQL migrations and OpenAPI,
and run all quality checks locally.
