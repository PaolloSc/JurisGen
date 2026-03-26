@echo off
REM Uso: update_tunnel_url.bat https://xxx.trycloudflare.com
REM Atualiza _redirects e faz push automaticamente

if "%~1"=="" (
    echo Uso: update_tunnel_url.bat https://xxx.trycloudflare.com
    exit /b 1
)

set "TUNNEL_URL=%~1"
set "REPO_DIR=%~dp0"
set "REDIRECTS=%REPO_DIR%frontend\public\_redirects"

echo Atualizando _redirects com: %TUNNEL_URL%

echo /api/*  %TUNNEL_URL%/api/:splat  200 > "%REDIRECTS%"
echo /*    /index.html   200 >> "%REDIRECTS%"

cd /d "%REPO_DIR%"
git add frontend/public/_redirects
git commit -m "fix: update backend tunnel URL to %TUNNEL_URL%"
git push origin main

echo.
echo Pronto! Trapiche.cloud vai reconstruir o frontend automaticamente.
echo Aguarde ~1 minuto e acesse: https://jurisgen-proud-tiger.trapiche.site
