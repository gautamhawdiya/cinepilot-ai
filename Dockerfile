# CinePilot AI backend (FastAPI + Google ADK agents) for Cloud Run.
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agents/ agents/
COPY api/ api/
COPY pdf/ pdf/
COPY schemas/ schemas/
COPY tools/ tools/
COPY validators/ validators/

RUN mkdir -p outputs/projects

# Cloud Run injects PORT; default to 8080 for local `docker run`.
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
