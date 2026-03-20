#!/bin/bash
# ============================================================
# JurisGen AI - Script de Deploy para Ubuntu Server (Azure VM)
# ============================================================
# Uso: ssh para a VM e execute:
#   curl -sSL https://raw.githubusercontent.com/SEU_REPO/main/deploy.sh | bash
# Ou copie este arquivo para a VM e execute: bash deploy.sh
# ============================================================

set -e

echo "=========================================="
echo "  JurisGen AI - Deploy em Produção"
echo "=========================================="

# 1. Atualizar sistema
echo "[1/8] Atualizando sistema..."
sudo apt-get update -y && sudo apt-get upgrade -y

# 2. Instalar dependências
echo "[2/8] Instalando Node.js 20, Python 3.12, Nginx, Git..."
sudo apt-get install -y curl git nginx software-properties-common

# Node.js 20
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi

# Python 3.12
if ! command -v python3.12 &> /dev/null; then
    sudo add-apt-repository -y ppa:deadsnakes/ppa
    sudo apt-get update -y
    sudo apt-get install -y python3.12 python3.12-venv python3.12-dev python3-pip
fi

echo "  Node: $(node --version)"
echo "  Python: $(python3.12 --version 2>&1 || python3 --version)"

# 3. Instalar Claude Code CLI
echo "[3/8] Instalando Claude Code CLI..."
sudo npm install -g @anthropic-ai/claude-code

# 4. Configurar diretório da aplicação
echo "[4/8] Configurando aplicação..."
APP_DIR="/opt/jurisgen"
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR

# Copiar arquivos (assumindo que estão no diretório atual)
if [ -d "./backend" ] && [ -d "./frontend" ]; then
    cp -r ./backend $APP_DIR/
    cp -r ./frontend $APP_DIR/
else
    echo "ERRO: Diretórios backend/ e frontend/ não encontrados."
    echo "Execute este script a partir da pasta jurisgen/"
    exit 1
fi

# 5. Setup Backend
echo "[5/8] Configurando backend..."
cd $APP_DIR/backend

python3.12 -m venv venv || python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# Criar .env se não existir
if [ ! -f ".env" ]; then
    echo "AVISO: Crie o arquivo $APP_DIR/backend/.env com suas credenciais!"
    cp .env.example .env 2>/dev/null || true
fi

# 6. Build Frontend
echo "[6/8] Fazendo build do frontend..."
cd $APP_DIR/frontend
npm install

# Em produção, VITE_API_BASE vazio = usa caminho relativo (nginx faz proxy)
VITE_API_BASE="" npm run build

# 7. Configurar Nginx
echo "[7/8] Configurando Nginx..."
DOMAIN="${JURISGEN_DOMAIN:-_}"

sudo tee /etc/nginx/sites-available/jurisgen > /dev/null <<NGINX
server {
    listen 80;
    server_name $DOMAIN;

    # Frontend (arquivos estáticos)
    root $APP_DIR/frontend/dist;
    index index.html;

    # SPA: todas as rotas vão para index.html
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # Proxy API para o backend
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # Health check direto
    location /health {
        proxy_pass http://127.0.0.1:8000;
    }

    # Tamanho máximo de upload (para documentos)
    client_max_body_size 50M;
}
NGINX

sudo ln -sf /etc/nginx/sites-available/jurisgen /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

# 8. Criar serviço systemd para o backend
echo "[8/8] Criando serviço systemd..."
sudo tee /etc/systemd/system/jurisgen.service > /dev/null <<SERVICE
[Unit]
Description=JurisGen AI Backend
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR/backend
Environment=PATH=$APP_DIR/backend/venv/bin:/usr/local/bin:/usr/bin:/bin
EnvironmentFile=$APP_DIR/backend/.env
ExecStart=$APP_DIR/backend/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable jurisgen
sudo systemctl start jurisgen

echo ""
echo "=========================================="
echo "  Deploy concluído!"
echo "=========================================="
echo ""
echo "PRÓXIMOS PASSOS OBRIGATÓRIOS:"
echo ""
echo "1. Faça login no Claude CLI (uma única vez):"
echo "   claude login"
echo ""
echo "2. Edite o .env com suas credenciais reais:"
echo "   nano $APP_DIR/backend/.env"
echo ""
echo "3. Reinicie o backend após configurar:"
echo "   sudo systemctl restart jurisgen"
echo ""
echo "4. (Opcional) Adicione HTTPS com Let's Encrypt:"
echo "   sudo apt install certbot python3-certbot-nginx"
echo "   sudo certbot --nginx -d seu-dominio.com"
echo ""
echo "5. Verifique se está funcionando:"
echo "   curl http://localhost/health"
echo "   sudo systemctl status jurisgen"
echo ""
echo "Logs do backend:"
echo "   sudo journalctl -u jurisgen -f"
echo ""
