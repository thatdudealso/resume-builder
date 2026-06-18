FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
    libffi-dev shared-mime-info curl libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY apps apps
COPY packages packages
COPY migrations migrations
COPY alembic.ini ./
COPY scripts scripts

RUN pip install --no-cache-dir -e ".[dev]"

ENV PYTHONPATH=/app
EXPOSE 8000

CMD ["uvicorn", "apps.web.main:app", "--host", "0.0.0.0", "--port", "8000"]
