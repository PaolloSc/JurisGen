#!/usr/bin/env bash
# export_claude_credentials.sh
# Exporta as credenciais OAuth do Claude CLI local para uma string Base64.
# Cole o resultado no campo CLAUDE_CREDENTIALS_B64 do dashboard do Render.
#
# Uso:
#   bash export_claude_credentials.sh
#
# Pré-requisitos:
#   - Claude CLI instalado e autenticado localmente via `claude login`
#   - Credenciais em ~/.claude/.credentials.json  (Linux/Mac)
#     ou em %USERPROFILE%\.claude\.credentials.json (Windows/Git Bash)

set -e

CRED_FILE="${HOME}/.claude/.credentials.json"

# Tenta o USERPROFILE do Windows se HOME não tiver o arquivo
if [ ! -f "$CRED_FILE" ] && [ -n "$USERPROFILE" ]; then
    WIN_CRED="$(cygpath -u "$USERPROFILE" 2>/dev/null || echo "$USERPROFILE")/.claude/.credentials.json"
    if [ -f "$WIN_CRED" ]; then
        CRED_FILE="$WIN_CRED"
    fi
fi

if [ ! -f "$CRED_FILE" ]; then
    echo "ERRO: Arquivo de credenciais não encontrado em $CRED_FILE"
    echo "Execute primeiro: claude login"
    exit 1
fi

echo ""
echo "=== Credenciais Claude CLI para o Render ==="
echo ""
echo "Copie a linha abaixo e cole em CLAUDE_CREDENTIALS_B64 no Render:"
echo ""
base64 -w0 "$CRED_FILE"
echo ""
echo ""
echo "Arquivo de origem: $CRED_FILE"
echo "=== Fim ==="
