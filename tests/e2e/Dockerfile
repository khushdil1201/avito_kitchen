FROM python:3.12-slim AS test

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system test && useradd --system --gid test test

COPY pyproject.toml README.md ./
COPY services/kitchen-api/src ./services/kitchen-api/src
COPY services/restaurant-api/src ./services/restaurant-api/src

RUN python -m pip install . "pytest>=8.4,<9"

COPY tests/e2e ./tests/e2e

USER test

CMD ["pytest", "-p", "no:cacheprovider", "-m", "e2e", "tests/e2e", "-v"]
