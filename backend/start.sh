#!/bin/bash
# start.sh — Startup script para o backend JurisGen no Render/Docker
#
# Fluxo:
#   1. Restaura credenciais OAuth do Claude CLI a partir de CLAUDE_CREDENTIALS_B64
#   2. Executa diagnóstico rápido do ambiente Claude CLI
#   3. Inicia o servidor uvicorn
#
# Autenticação: OAuth via CLAUDE_CREDENTIALS_B64 (sem ANTHROPIC_API_KEY)

set -e

# ── 1. Restaurar credenciais OAuth do Claude CLI ──────────────────────────────
if [ -n "$CLAUDE_CREDENTIALS_B64" ]; then
    CLAUDE_DIR="${HOME}/.claude"
    mkdir -p "$CLAUDE_DIR"
    echo "$CLAUDE_CREDENTIALS_B64" | base64 -d > "$CLAUDE_DIR/.credentials.json"
    chmod 600 "$CLAUDE_DIR/.credentials.json"
    echo "[startup] Claude CLI credentials restored to $CLAUDE_DIR/.credentials.json"
else
    echo "[startup] CLAUDE_CREDENTIALS_B64 not set"
    echo "[startup] Claude CLI will fall back to MARITACA_API_KEY if available"
    echo "[startup] To enable Claude CLI: set CLAUDE_CREDENTIALS_B64 in the Render dashboard"
    echo "[startup]   (run: bash export_claude_credentials.sh  to generate the value locally)"
fi

# ── 2. Diagnóstico rápido (sem chamada de API — só variáveis e binário) ───────
echo ""
echo "[startup] Running quick environment check..."
python check_claude_env.py --quick || true
echo ""

# ── 3. Iniciar uvicorn ────────────────────────────────────────────────────────
echo "[startup] Starting uvicorn on port ${PORT:-8000}..."
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
