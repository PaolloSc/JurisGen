@echo off
echo ============================================
echo  JurisGen - Iniciando Backend (sem Docker)
echo ============================================

cd /d "%~dp0backend"

REM Criar venv se nao existir
if not exist "venv\Scripts\activate.bat" (
    echo [1/3] Criando ambiente virtual Python...
    python -m venv venv
)

REM Ativar venv e instalar dependencias
echo [2/3] Instalando dependencias...
call venv\Scripts\activate.bat
pip install -r requirements.txt --quiet

REM Criar .env se nao existir
if not exist ".env" (
    echo [AVISO] Arquivo .env nao encontrado. Copiando .env.example...
    copy .env.example .env
    echo [AVISO] Edite backend\.env com suas credenciais antes de usar!
)

echo [3/3] Iniciando backend em http://localhost:8000
echo.
echo Para expor publicamente (nova janela), execute: expose_backend.bat
echo Pressione Ctrl+C para parar.
echo.

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
