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

# Cria o diretório para as credenciais do Claude
RUN mkdir -p /root/.claude

# Comando final: decodifica as credenciais + inicia o uvicorn
CMD bash -c '\
    if [ -n "$CLAUDE_CREDENTIALS_B64" ]; then \
        echo "$CLAUDE_CREDENTIALS_B64" | base64 -d > /root/.claude/.credentials.json && \
        echo "✅ Credenciais do Claude decodificadas com sucesso em /root/.claude/.credentials.json"; \
    else \
        echo "⚠️  AVISO: Variável CLAUDE_CREDENTIALS_B64 não foi definida"; \
    fi && \
    uvicorn main:app --host 0.0.0.0 --port $PORT'
