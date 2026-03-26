@echo off
echo ============================================
echo  JurisGen - Expondo backend via Cloudflare
echo ============================================
echo.
echo Aguarde a URL publica aparecer abaixo...
echo Copie a URL https://xxx.trycloudflare.com
echo e adicione como secret VITE_API_BASE no GitHub.
echo.
echo Pressione Ctrl+C para encerrar o tunnel.
echo.

cloudflared tunnel --url http://localhost:8000
