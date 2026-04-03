@echo off
echo ============================================
echo   Loan Test Case Engine - One-Time Setup
echo ============================================
echo.
echo Prerequisites:
echo   - Python 3.11+
echo   - Node.js 18+
echo   - Docker Desktop
echo   - Git
echo.
echo Press any key to begin setup...
pause >nul
echo.

:: Check prerequisites
echo [1/7] Checking prerequisites...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python not found. Install Python 3.11+ from https://python.org
    pause
    exit /b 1
)
node --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Node.js not found. Install Node.js 18+ from https://nodejs.org
    pause
    exit /b 1
)
docker --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Docker not found. Install Docker Desktop from https://docker.com
    pause
    exit /b 1
)
echo       All prerequisites found.
echo.

:: Start Docker containers
echo [2/7] Starting Docker containers (PostgreSQL + Redis)...
cd /d %~dp0..
docker compose up -d db redis
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to start Docker containers. Is Docker Desktop running?
    pause
    exit /b 1
)
echo       Docker containers started.
echo.

:: Wait for DB
echo [3/7] Waiting for PostgreSQL to be ready...
timeout /t 5 /nobreak >nul
echo       PostgreSQL ready.
echo.

:: Install backend dependencies
echo [4/7] Installing backend Python dependencies...
cd /d %~dp0..\backend
pip install -e ".[dev]"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install Python dependencies.
    pause
    exit /b 1
)
echo       Backend dependencies installed.
echo.

:: Set up environment file
echo [5/7] Setting up environment...
if not exist "%~dp0..\backend\.env" (
    echo DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/policy_impact_engine> "%~dp0..\backend\.env"
    echo REDIS_URL=redis://localhost:6379/0>> "%~dp0..\backend\.env"
    echo OPENAI_API_KEY=your-openai-key-here>> "%~dp0..\backend\.env"
    echo       Created backend/.env - IMPORTANT: Update OPENAI_API_KEY!
) else (
    echo       backend/.env already exists, skipping.
)
echo.

:: Initialize database tables
echo [6/7] Initializing database and seeding data...
cd /d %~dp0..\backend
python -c "import asyncio; from app.database import engine; from app.models import Base; asyncio.run(Base.metadata.create_all(bind=engine))" 2>nul
python -m scripts.seed_loan_records 2>nul
if %ERRORLEVEL% EQU 0 (
    echo       Database seeded with 10,000 loan records.
) else (
    echo       Note: Seed script may need to run after first backend start.
    echo       Start the app once, then run: python -m scripts.seed_loan_records
)
echo.

:: Install frontend dependencies
echo [7/7] Installing frontend dependencies...
cd /d %~dp0..\frontend
npm install
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install frontend dependencies.
    pause
    exit /b 1
)
echo       Frontend dependencies installed.
echo.

:: Stop Docker containers (user can start fresh with start.bat)
echo Stopping Docker containers (use start.bat to run the app)...
cd /d %~dp0..
docker compose down

echo.
echo ============================================
echo   Setup Complete!
echo ============================================
echo.
echo   IMPORTANT: Edit backend/.env and set your OPENAI_API_KEY
echo.
echo   To start the app:  scripts\start.bat
echo   To stop the app:   scripts\stop.bat
echo.
echo ============================================
pause
