@echo off
echo ============================================
echo   Loan Test Case Engine - Stopping...
echo ============================================
echo.

:: Kill backend
echo [1/3] Stopping Backend (Python/Uvicorn)...
taskkill /F /IM python.exe >nul 2>&1
echo       Backend stopped.

:: Kill frontend
echo [2/3] Stopping Frontend (Node.js)...
taskkill /F /IM node.exe >nul 2>&1
echo       Frontend stopped.

:: Stop Docker containers
echo [3/3] Stopping Docker containers...
docker compose down
echo       Docker containers stopped.

echo.
echo ============================================
echo   All services stopped.
echo ============================================
pause
