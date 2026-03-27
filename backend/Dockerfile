FROM python:3.12-slim

WORKDIR /app

# Install system deps + Node.js 20 LTS
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gcc git ca-certificates xz-utils && \
    curl -fsSL https://nodejs.org/dist/v20.11.0/node-v20.11.0-linux-x64.tar.xz \
    | tar -xJ -C /usr/local --strip-components=1 && \
    rm -rf /var/lib/apt/lists/*

# Install Claude CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Install Python dependencies
COPY requirements_minimal.txt .
RUN pip install --no-cache-dir -r requirements_minimal.txt

COPY . .

ENV PORT=8000

EXPOSE $PORT

CMD uvicorn main:app --host 0.0.0.0 --port $PORT
