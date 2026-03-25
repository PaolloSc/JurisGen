#!/bin/bash
# ============================================================
# JurisGen AI — Quick Tunnel (Cloudflare trycloudflare.com)
# ============================================================
# Use para testes rápidos SEM domínio próprio.
# Cada execução gera uma URL diferente (ex: xxx.trycloudflare.com).
#
# Uso: bash cloudflare/quick-tunnel.sh
#
# Requisitos:
#   - Docker stack rodando: docker compose up -d
#   - cloudflared instalado no host
# ============================================================

set -e

echo "Verificando se o stack Docker está rodando..."
if ! curl -sf http://localhost/api/health > /dev/null 2>&1 && \
   ! curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "AVISO: Backend pode não estar rodando. Verifique com: docker compose ps"
fi

echo ""
echo "Iniciando Quick Tunnel para http://localhost:80 ..."
echo "Uma URL trycloudflare.com será gerada. Copie-a para acessar o JurisGen."
echo "Pressione Ctrl+C para encerrar."
echo ""

cloudflared tunnel --url http://localhost:80
