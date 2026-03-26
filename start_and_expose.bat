@echo off
setlocal enabledelayedexpansion

echo ============================================
echo  JurisGen - Backend + Tunnel Automatico
echo ============================================

set "REPO_DIR=%~dp0"
set "BACKEND_DIR=%~dp0backend"

REM ── 1. Iniciar backend em background ──────────────────────────
echo [1/3] Iniciando backend...
cd /d "%BACKEND_DIR%"

if not exist "venv\Scripts\activate.bat" (
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install fastapi "uvicorn[standard]" httpx python-dotenv python-docx pydantic python-multipart reportlab msal duckduckgo-search openai --quiet
pip install pymupdf --only-binary=:all: --quiet 2>nul

if not exist ".env" (
    copy .env.example .env >nul 2>&1
)

start "JurisGen Backend" cmd /c "call venv\Scripts\activate.bat && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

echo    Backend iniciando em http://localhost:8000
echo    Aguardando 5 segundos...
timeout /t 5 /nobreak >nul

REM ── 2. Iniciar tunnel e capturar URL ──────────────────────────
echo [2/3] Iniciando tunnel cloudflared...
cd /d "%REPO_DIR%"

REM Executar cloudflared e capturar a URL do tunnel
set "TUNNEL_LOG=%TEMP%\jurisgen_tunnel.log"
start "JurisGen Tunnel" cmd /c "cloudflared tunnel --url http://localhost:8000 2>%TUNNEL_LOG%"

echo    Aguardando URL do tunnel (ate 30 segundos)...
set "TUNNEL_URL="
for /l %%i in (1,1,30) do (
    timeout /t 1 /nobreak >nul
    if exist "%TUNNEL_LOG%" (
        for /f "tokens=*" %%a in ('findstr /i "trycloudflare.com" "%TUNNEL_LOG%" 2^>nul') do (
            for /f "tokens=* delims= " %%b in ("%%a") do (
                echo %%b | findstr /i "https://" >nul 2>&1
                if not errorlevel 1 (
                    REM Extract URL from log line
                    for /f "tokens=*" %%c in ('echo %%b ^| findstr /o "https://[^ ]*trycloudflare"') do (
                        set "TUNNEL_URL=%%c"
                    )
                )
            )
        )
    )
    if defined TUNNEL_URL goto :got_url
)

:got_url
if not defined TUNNEL_URL (
    echo [AVISO] Nao foi possivel capturar a URL automaticamente.
    echo         Verifique a janela do tunnel e atualize manualmente:
    echo         public\_redirects linha 1: /api/*  https://URL.trycloudflare.com/api/:splat  200
    goto :manual
)

echo [3/3] URL do tunnel: !TUNNEL_URL!

REM Atualizar _redirects
set "REDIRECTS=%REPO_DIR%frontend\public\_redirects"
echo /api/*  !TUNNEL_URL!/api/:splat  200 > "%REDIRECTS%"
echo /*    /index.html   200 >> "%REDIRECTS%"

echo    Atualizando repositorio...
cd /d "%REPO_DIR%"
git add frontend/public/_redirects
git commit -m "fix: update backend tunnel URL in _redirects"
git push origin main

echo.
echo ============================================
echo  Tudo pronto!
echo  Frontend: https://jurisgen-proud-tiger.trapiche.site
echo  Backend:  !TUNNEL_URL!
echo  Deploy:   trapiche.cloud vai reconstruir automaticamente
echo ============================================
goto :end

:manual
echo.
echo Apos obter a URL, execute:
echo   update_tunnel_url.bat SUA_URL_AQUI
echo.

:end
echo.
echo Pressione qualquer tecla para fechar (backend e tunnel continuam rodando)
pause >nul
