ARG PYTHON_VERSION=3.13
FROM python:${PYTHON_VERSION}-alpine

LABEL org.opencontainers.image.source="https://github.com/Sudo-Ivan/rns-page-node"
LABEL org.opencontainers.image.description="A simple way to serve pages and files over the Reticulum network."
LABEL org.opencontainers.image.licenses="GPL-3.0"
LABEL org.opencontainers.image.authors="Sudo-Ivan"

WORKDIR /app

RUN pip install poetry

COPY pyproject.toml poetry.lock* ./
COPY README.md ./
COPY rns_page_node ./rns_page_node

RUN poetry install --no-root --no-interaction --no-ansi

ENTRYPOINT ["rns-page-node"]
