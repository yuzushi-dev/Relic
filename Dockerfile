# Scientific reproducibility container for RELIC/GUMI evaluation artifacts.
FROM python:3.12.3-slim-bookworm

ARG UV_VERSION=0.8.15
ARG RELIC_SOURCE_COMMIT=unknown
ARG RELIC_SOURCE_BRANCH=unknown

LABEL org.opencontainers.image.title="relic-oss scientific evaluation environment"
LABEL org.opencontainers.image.description="Pinned Python/uv environment for local RELIC/GUMI evaluation reports"
LABEL org.opencontainers.image.revision="${RELIC_SOURCE_COMMIT}"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/workspace/relic-oss
ENV RELIC_SOURCE_COMMIT=${RELIC_SOURCE_COMMIT}
ENV RELIC_SOURCE_BRANCH=${RELIC_SOURCE_BRANCH}
ENV UV_PROJECT_ENVIRONMENT=/opt/relic-venv
ENV UV_LINK_MODE=copy
ENV PATH="/opt/relic-venv/bin:${PATH}"

WORKDIR /workspace/relic-oss

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir "uv==${UV_VERSION}"

COPY pyproject.toml uv.lock README.md Dockerfile .dockerignore ./
COPY fixtures ./fixtures
COPY relic ./relic
COPY scripts ./scripts
COPY tests ./tests
COPY docs ./docs
COPY public-docs ./public-docs

RUN uv sync --locked --extra dev

CMD ["python", "scripts/eval_run.py", "--experiment", "scientific_defensibility_gate", "--json"]
