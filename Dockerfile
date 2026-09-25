FROM python:3.12-slim
WORKDIR /srv
COPY pyproject.toml ./
COPY app ./app
COPY config ./config
COPY alembic ./alembic
COPY alembic.ini ./
RUN pip install --no-cache-dir .
