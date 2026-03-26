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

REM Instalar dependencias - so wheels pre-compilados (sem compilar C extensions)
echo [2/3] Instalando dependencias...
pip install --upgrade pip --quiet

REM Instalar pacotes basicos (todos tem wheels para Python 3.x)
pip install fastapi "uvicorn[standard]" httpx python-dotenv python-docx pydantic python-multipart reportlab msal duckduckgo-search openai --quiet

REM pymupdf pode nao ter wheel para Python 3.14 - tentar com binary only
pip install pymupdf --only-binary=:all: --quiet 2>nul && echo   pymupdf OK || echo   [AVISO] pymupdf ignorado

REM Pacotes ML opcionais (RAG) - podem falhar em Python 3.14
pip install "chromadb>=0.5.0" --only-binary=:all: --quiet 2>nul && echo   chromadb OK || echo   [AVISO] chromadb ignorado (RAG desabilitado)
pip install "sentence-transformers>=3.0.0" --only-binary=:all: --quiet 2>nul && echo   sentence-transformers OK || echo   [AVISO] sentence-transformers ignorado
pip install "docling>=2.0.0" --only-binary=:all: --quiet 2>nul && echo   docling OK || echo   [AVISO] docling ignorado

REM Criar .env se nao existir
if not exist ".env" (
    echo [AVISO] Copiando .env.example para .env...
    copy .env.example .env
    echo [AVISO] Edite backend\.env com suas credenciais!
)

echo.
echo [3/3] Iniciando backend em http://localhost:8000
echo Para expor publicamente abra outra janela e execute: expose_backend.bat
echo Pressione Ctrl+C para parar.
echo.

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
