# MedWise BD backend. Build from the repository root (it needs data/seed):
#   docker build -f backend/Dockerfile .
FROM python:3.11.9-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Same layout as the repo, so app/core/config.py finds data/seed without changes.
WORKDIR /app/backend
COPY backend/requirements.txt .
# Exact pins (see requirements.txt); --no-deps + pip check means nothing unlisted gets in.
RUN pip install --no-deps -r requirements.txt && pip check

COPY backend/ .
COPY data/seed/ /app/data/seed/

RUN useradd --create-home --uid 10001 medwise
USER medwise

EXPOSE 8000
# Load the seed files into the database on every start (the import validates every row),
# then serve the API.
CMD ["sh", "-c", "python scripts/import_data.py && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
