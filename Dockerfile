# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:0.8.12 AS uv
FROM python:3.12.4-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app
COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md ./
COPY src/coldchain ./src/coldchain
COPY alembic.ini ./
COPY alembic ./alembic
COPY sop ./sop
RUN uv sync --frozen --no-dev

RUN addgroup --system coldchain && adduser --system --ingroup coldchain coldchain
USER coldchain

EXPOSE 8000
CMD ["uvicorn", "coldchain.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

FROM runtime AS test
USER root
COPY tests ./tests
COPY contracts ./contracts
COPY scripts ./scripts
RUN uv sync --frozen --all-groups
RUN chown -R coldchain:coldchain /app
USER coldchain
CMD ["pytest", "-q"]
