# syntax=docker/dockerfile:1
FROM python:3.12-slim AS runtime
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml requirements.lock requirements-runtime.lock ./
RUN --mount=type=cache,target=/root/.cache/pip pip install --timeout 120 -r requirements-runtime.lock
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY tool-fixtures /opt/opspilot/tool-fixtures
COPY tool-repository /opt/opspilot/tool-repository
RUN git -C /opt/opspilot/tool-repository init \
    && git -C /opt/opspilot/tool-repository config user.name "OpsPilot Fixture" \
    && git -C /opt/opspilot/tool-repository config user.email "fixture@opspilot.local" \
    && git -C /opt/opspilot/tool-repository add . \
    && git -C /opt/opspilot/tool-repository commit -m "Add recommendation service regression fixture"
RUN useradd --uid 10001 --create-home opspilot
USER opspilot
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]

FROM runtime AS test
USER root
RUN --mount=type=cache,target=/root/.cache/pip pip install --timeout 120 -c requirements.lock pytest pytest-asyncio httpx aiosqlite
COPY tests ./tests
USER opspilot
CMD ["python", "-m", "pytest", "-q", "-o", "cache_dir=/tmp/pytest-cache"]
