#!/bin/bash
# ============================================================
# JurisGen AI — Deploy com Cloudflare Tunnel
# ============================================================
# Executa em um servidor Linux com Docker instalado.
# Uso: bash cloudflare/deploy-cloudflare.sh
# ============================================================

set -e

APP_DIR="/opt/jurisgen"
TUNNEL_CONFIG="$APP_DIR/cloudflare/tunnel.yml"

echo "=========================================="
echo "  JurisGen AI — Deploy Cloudflare"
echo "=========================================="

# 1. Instalar cloudflared (se não instalado)
if ! command -v cloudflared &> /dev/null; then
    echo "[1/6] Instalando cloudflared..."
    curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb \
         -o /tmp/cloudflared.deb
    sudo dpkg -i /tmp/cloudflared.deb
else
    echo "[1/6] cloudflared já instalado: $(cloudflared --version)"
fi

# 2. Configurar diretório da aplicação
echo "[2/6] Configurando diretório $APP_DIR..."
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR

if [ -d "./backend" ] && [ -d "./frontend" ]; then
    cp -r . $APP_DIR/
else
    echo "ERRO: Execute a partir da pasta jurisgen/"
    exit 1
fi

cd $APP_DIR

# 3. Configurar .env (se não existir)
echo "[3/6] Verificando .env..."
if [ ! -f "./backend/.env" ]; then
    cp ./backend/.env.example ./backend/.env
    echo ""
    echo "⚠️  ATENÇÃO: Configure ./backend/.env com suas credenciais antes de continuar!"
    echo "   Pressione Enter após configurar..."
    read
fi

# 4. Iniciar stack Docker (backend + frontend + ollama)
echo "[4/6] Iniciando containers Docker..."
docker compose pull
docker compose up -d --build

echo "   Aguardando Ollama inicializar..."
sleep 10

echo "   Aguardando modelo Jurema ser carregado..."
# Espera até 5 minutos pelo ollama-setup terminar
timeout 300 bash -c 'until docker compose logs ollama-setup 2>&1 | grep -q "Jurema 7B pronto"; do sleep 5; done' || true

echo "   Stack iniciado. Verificando saúde..."
sleep 5
curl -sf http://localhost:8000/health && echo " Backend OK" || echo " Backend ainda iniciando..."

# 5. Configurar Cloudflare Tunnel como serviço
echo "[5/6] Configurando Cloudflare Tunnel..."

if [ ! -f "$TUNNEL_CONFIG" ]; then
    echo "ERRO: $TUNNEL_CONFIG não encontrado."
    echo "      Configure cloudflare/tunnel.yml com seu TUNNEL_ID."
    exit 1
fi

# Verificar se está autenticado
if [ ! -d "$HOME/.cloudflared" ]; then
    echo ""
    echo "⚠️  Faça login no Cloudflare primeiro:"
    echo "   cloudflared tunnel login"
    echo "   cloudflared tunnel create jurisgen"
    echo "   (Anote o TUNNEL_ID e atualize cloudflare/tunnel.yml)"
    echo ""
    echo "Pressione Enter após configurar..."
    read
fi

# Instalar como serviço systemd
sudo cloudflared service install --config $TUNNEL_CONFIG
sudo systemctl enable cloudflared
sudo systemctl start cloudflared

# 6. Verificar status
echo "[6/6] Verificando status final..."
echo ""
docker compose ps
echo ""
sudo systemctl status cloudflared --no-pager -l | head -20

echo ""
echo "=========================================="
echo "  Deploy concluído!"
echo "=========================================="
echo ""
echo "  App:  https://jurisgen.seu-dominio.com"
echo "  API:  https://api.jurisgen.seu-dominio.com/docs"
echo ""
echo "Logs do tunnel:  sudo journalctl -u cloudflared -f"
echo "Logs do backend: docker compose logs -f backend"
echo "Logs do Ollama:  docker compose logs -f ollama"
