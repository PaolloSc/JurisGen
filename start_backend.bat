@echo off
echo ============================================
echo  JurisGen - Iniciando Backend Local
echo ============================================
echo.

cd /d "%~dp0backend"

if not exist "venv\Scripts\activate.bat" (
    echo Criando ambiente virtual Python...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo Instalando dependencias...
pip install fastapi "uvicorn[standard]" httpx python-dotenv python-docx pydantic python-multipart reportlab msal duckduckgo-search openai --quiet
pip install pymupdf --only-binary=:all: --quiet 2>nul

if not exist ".env" (
    copy .env.example .env >nul 2>&1
    echo AVISO: Edite backend\.env com suas credenciais!
)

echo.
echo Backend iniciando em http://localhost:8000 (Claude CLI)
echo Pressione Ctrl+C para parar.
echo.

set CLAUDE_AUTH_MODE=cli
set LLM_PROVIDER=claude_cli
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
