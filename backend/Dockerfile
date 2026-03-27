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
ENV CLAUDE_AUTH_MODE=cli
ENV LLM_PROVIDER=claude_cli

EXPOSE $PORT

# Write credentials from env var (if set) then start server
CMD bash -c '\
  mkdir -p ~/.claude && \
  if [ -n "$CLAUDE_CREDENTIALS_B64" ]; then \
    echo "$CLAUDE_CREDENTIALS_B64" | base64 -d > ~/.claude/.credentials.json; \
  fi && \
  uvicorn main:app --host 0.0.0.0 --port $PORT'
