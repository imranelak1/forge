FROM python:3.13-slim-bookworm@sha256:2325bb286ec344af3e5898cc224b5844e2707ac6e26b1632516fd3edc84a5e26 AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

FROM base AS dependencies
RUN pip install --no-cache-dir uv==0.12.17
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM dependencies AS test
RUN uv sync --frozen --no-install-project
COPY . .
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app/src
CMD ["pytest", "-q"]

FROM base AS runtime
RUN groupadd --gid 10001 forge && useradd --uid 10001 --gid forge --no-create-home forge
RUN mkdir -p /app/.local/mail && chown -R forge:forge /app/.local
COPY --from=dependencies /app/.venv /app/.venv
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app/src
USER forge
EXPOSE 8000
CMD ["python", "-m", "forge.entrypoint"]
