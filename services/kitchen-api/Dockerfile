FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app app

COPY pyproject.toml README.md ./
COPY services/kitchen-api/src ./services/kitchen-api/src
COPY migrations ./migrations

RUN python -m pip install .

USER app

EXPOSE 8000

CMD ["uvicorn", "avito_kitchen.main:app", "--host", "0.0.0.0", "--port", "8000"]
