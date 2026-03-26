@echo off
REM Uso: update_tunnel_url.bat https://SEU-BACKEND.up.railway.app
REM Atualiza _redirects com a URL do backend e faz push

if "%~1"=="" (
    echo Uso: update_tunnel_url.bat https://SEU-BACKEND.up.railway.app
    exit /b 1
)

REM Strip trailing slashes and dots from URL
set "BACKEND_URL=%~1"
set "BACKEND_URL=%BACKEND_URL:/=%"
for /f "tokens=*" %%a in ('powershell -command "('%~1').TrimEnd('/.')"') do set "BACKEND_URL=%%a"
set REDIRECTS=%~dp0frontend\public\_redirects

echo /api/*  %BACKEND_URL%/api/:splat  200 > "%REDIRECTS%"
echo /*    /index.html   200 >> "%REDIRECTS%"

cd /d "%~dp0"
git add frontend/public/_redirects
git commit -m "fix: update backend URL to %BACKEND_URL%"
git push origin main

echo.
echo Pronto! Acesse: https://jurisgen-proud-tiger.trapiche.site
