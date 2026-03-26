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

REM Ativar venv
call venv\Scripts\activate.bat

REM Instalar dependencias basicas primeiro (sem pacotes pesados de ML)
echo [2/3] Instalando dependencias...
pip install -r requirements_minimal.txt --quiet

REM Tentar instalar pacotes ML opcionais (RAG/Docling) - pode falhar em Python 3.14
echo Instalando pacotes ML opcionais (pode demorar)...
pip install "chromadb>=0.5.0" --quiet 2>nul && echo   chromadb OK || echo   [AVISO] chromadb ignorado (incompativel com Python 3.14)
pip install "sentence-transformers>=3.0.0" --quiet 2>nul && echo   sentence-transformers OK || echo   [AVISO] sentence-transformers ignorado
pip install "docling>=2.0.0" --quiet 2>nul && echo   docling OK || echo   [AVISO] docling ignorado

REM Criar .env se nao existir
if not exist ".env" (
    echo [AVISO] Arquivo .env nao encontrado. Copiando .env.example...
    copy .env.example .env
    echo [AVISO] Edite backend\.env com suas credenciais antes de usar!
)

echo.
echo [3/3] Iniciando backend em http://localhost:8000
echo Para expor publicamente, abra outra janela e execute: expose_backend.bat
echo Pressione Ctrl+C para parar.
echo.

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
