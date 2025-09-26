For use case with BERT, cant use alphine, have to use slim

FROM python:3.12-slim AS build

WORKDIR /app

# system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy all code into /app
COPY . .

# Install Poetry and dependencies
RUN pip install poetry==2.1.2 --no-cache-dir && \
    poetry config virtualenvs.create false && \
    poetry install --without process_checks