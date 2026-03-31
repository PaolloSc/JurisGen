FROM python:3.12-slim

WORKDIR /app

# Install system deps + Node.js 20 LTS (via tarball — pinned version for reproducibility)
# curl: health check; gcc: Python native builds; git: Claude CLI internals
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gcc git ca-certificates xz-utils && \
    curl -fsSL https://nodejs.org/dist/v20.11.0/node-v20.11.0-linux-x64.tar.xz \
    | tar -xJ -C /usr/local --strip-components=1 && \
    rm -rf /var/lib/apt/lists/*

# Install Claude CLI globally (no API key required — uses OAuth via CLAUDE_CREDENTIALS_B64)
RUN npm install -g @anthropic-ai/claude-code

# Install Python dependencies
COPY backend/requirements_minimal.txt .
RUN pip install --no-cache-dir -r requirements_minimal.txt

COPY backend/ .

ENV PORT=8000

EXPOSE $PORT

# Pre-create credentials directory (start.sh writes here at runtime)
RUN mkdir -p /root/.claude && chmod +x start.sh export_claude_credentials.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# start.sh: restores OAuth credentials from CLAUDE_CREDENTIALS_B64, runs quick
# env diagnostic, then launches uvicorn. No ANTHROPIC_API_KEY needed.
CMD ["bash", "start.sh"]
