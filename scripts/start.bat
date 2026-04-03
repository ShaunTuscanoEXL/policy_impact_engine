@echo off
echo ============================================
echo   Loan Test Case Engine - Starting...
echo ============================================
echo.

:: Start Docker containers
echo [1/3] Starting Docker containers (PostgreSQL + Redis)...
docker compose up -d db redis
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to start Docker containers. Is Docker running?
    pause
    exit /b 1
)
echo       Docker containers started.
echo.

:: Wait for DB to be ready
echo [2/3] Waiting for PostgreSQL to be ready...
timeout /t 3 /nobreak >nul

:: Start Backend
echo [3/3] Starting Backend (port 8001) and Frontend (port 3000)...
start "Backend - Uvicorn" cmd /k "cd /d %~dp0..\backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload"
timeout /t 2 /nobreak >nul
start "Frontend - Next.js" cmd /k "cd /d %~dp0..\frontend && npm run dev"

echo.
echo ============================================
echo   All services starting!
echo   Backend:  http://localhost:8001
echo   Frontend: http://localhost:3000
echo ============================================
echo.
echo   Press any key to close this window.
echo   (Backend and Frontend will keep running)
pause >nul
