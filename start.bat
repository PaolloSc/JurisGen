@echo off
REM ============================================================
REM JurisGen AI - Iniciar stack no Windows
REM ============================================================

SET HOME=%USERPROFILE%
echo HOME=%HOME%

echo Verificando Docker Desktop...
docker info > /dev/null 2>&1
IF ERRORLEVEL 1 (
    echo.
    echo ============================================================
    echo  ERRO: Docker Desktop nao esta respondendo.
    echo ============================================================
    echo.
    echo Passos para corrigir:
    echo 1. Abra o Docker Desktop no menu Iniciar
    echo 2. Aguarde o icone da baleia parar de animar na barra de tarefas
    echo 3. Verifique que esta em modo "Linux containers":
    echo    - Clique com botao direito no icone Docker na barra
    echo    - Se aparecer "Switch to Linux containers", clique nele
    echo 4. Execute este script novamente
    echo.
    pause
    exit /b 1
)

echo Docker OK. Iniciando JurisGen AI...
echo.

REM Cria .env se nao existir
IF NOT EXIST "backend\.env" (
    echo AVISO: backend\.env nao encontrado. Copiando do exemplo...
    copy "backend\.env.example" "backend\.env"
    echo Edite backend\.env com suas credenciais antes de continuar.
    notepad "backend\.env"
)

docker compose up -d --build
IF ERRORLEVEL 1 (
    echo.
    echo ERRO ao iniciar. Verifique os logs acima.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  JurisGen AI iniciado com sucesso!
echo ============================================================
echo.
echo  Frontend:  http://localhost
echo  Backend:   http://localhost:8000/docs
echo  Ollama:    http://localhost:11434
echo.
echo  Logs:   docker compose logs -f
echo  Parar:  docker compose down
echo.
pause
