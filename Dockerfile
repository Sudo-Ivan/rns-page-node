FROM python:3.13-alpine

LABEL org.opencontainers.image.source="https://github.com/Sudo-Ivan/rns-page-node"
LABEL org.opencontainers.image.description="A simple way to serve pages and files over the Reticulum network."
LABEL org.opencontainers.image.licenses="GPL-3.0"
LABEL org.opencontainers.image.authors="Sudo-Ivan"

WORKDIR /app

COPY requirements.txt ./
COPY setup.py ./
COPY README.md ./
COPY rns_page_node ./rns_page_node

RUN pip install --upgrade pip setuptools wheel && pip install -r requirements.txt .

ENTRYPOINT ["rns-page-node"] 