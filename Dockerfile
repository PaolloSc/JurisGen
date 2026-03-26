FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gcc git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements_minimal.txt .
RUN pip install --no-cache-dir -r requirements_minimal.txt

COPY backend/ .

# PORT is injected by trapiche.cloud at runtime
ENV PORT=8000
EXPOSE $PORT

CMD uvicorn main:app --host 0.0.0.0 --port $PORT
