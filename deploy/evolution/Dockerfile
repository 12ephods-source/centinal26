FROM python:3.13-slim

ARG PYTEST_VERSION=9.1.1

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN python -m pip install --no-cache-dir "pytest==${PYTEST_VERSION}"

LABEL org.opencontainers.image.title="Centinal26 controlled-evolution validator" \
      org.opencontainers.image.description="Minimal validator runtime for fail-closed Docker candidate evaluation"

USER 65534:65534
WORKDIR /src
