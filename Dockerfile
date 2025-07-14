ARG PYTHON_VERSION=3.13
FROM python:${PYTHON_VERSION}-alpine

LABEL org.opencontainers.image.source="https://github.com/Sudo-Ivan/rns-page-node"
LABEL org.opencontainers.image.description="A simple way to serve pages and files over the Reticulum network."
LABEL org.opencontainers.image.licenses="GPL-3.0"
LABEL org.opencontainers.image.authors="Sudo-Ivan"

WORKDIR /app

RUN apk add --no-cache gcc python3-dev musl-dev linux-headers

RUN pip install poetry
ENV POETRY_VIRTUALENVS_IN_PROJECT=true

COPY pyproject.toml poetry.lock* ./
COPY README.md ./
COPY rns_page_node ./rns_page_node

RUN poetry install --no-interaction --no-ansi

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT ["poetry", "run", "rns-page-node"]
