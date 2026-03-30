#!/bin/bash
# Startup script: restore Claude CLI credentials then launch uvicorn

set -e

# ── Restore Claude CLI OAuth credentials ──────────────────────────────────────
if [ -n "$CLAUDE_CREDENTIALS_B64" ]; then
    CLAUDE_DIR="$HOME/.claude"
    mkdir -p "$CLAUDE_DIR"
    echo "$CLAUDE_CREDENTIALS_B64" | base64 -d > "$CLAUDE_DIR/.credentials.json"
    chmod 600 "$CLAUDE_DIR/.credentials.json"
    echo "[startup] Claude CLI credentials restored to $CLAUDE_DIR/.credentials.json"
else
    echo "[startup] CLAUDE_CREDENTIALS_B64 not set — Claude CLI will rely on ANTHROPIC_API_KEY or existing credentials"
fi

# ── Start the backend ─────────────────────────────────────────────────────────
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
