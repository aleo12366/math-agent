@echo off
REM ============================================================
REM Math Agent System - Windows Server Quick Deploy
REM ============================================================
REM Run as Administrator for service installation
REM ============================================================

echo.
echo ========================================
echo   Math Agent System - Windows Deploy
echo ========================================
echo.

cd /d "%~dp0"

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.11+ first.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js not found. Install Node.js 18+ first.
    echo Download: https://nodejs.org/
    pause
    exit /b 1
)

echo [1/4] Building frontend...
cd frontend
call npm install
call npm run build
cd ..
echo       Frontend built successfully!

echo.
echo [2/4] Setting up backend...
cd backend
if not exist "venv" (
    echo       Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat
python -m pip install --upgrade pip setuptools wheel >nul 2>&1
pip install -r requirements.txt
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env
        echo.
        echo       *** IMPORTANT ***
        echo       Edit backend\.env with your API key before starting!
        echo.
    )
)
cd ..
echo       Backend setup complete!

echo.
echo [3/4] Checking Nginx...
where nginx >nul 2>&1
if errorlevel 1 (
    echo       Nginx not found in PATH.
    echo       Option A: Download from https://nginx.org/en/download.html
    echo       Option B: Use deploy-windows.ps1 for auto-install
    echo.
    echo       You can also run without Nginx:
    echo       Backend only: cd backend ^& python main.py
    echo       Frontend dev: cd frontend ^& npm run dev
    echo.
) else (
    echo       Nginx found! Copy nginx-windows.conf to your nginx/conf/ dir.
)

echo.
echo [4/4] Starting backend (manual mode)...
echo.
echo ========================================
echo   Quick Start Commands:
echo ========================================
echo.
echo   Backend:   cd backend ^& venv\Scripts\activate ^& python main.py
echo   Frontend:  cd frontend ^& npm run dev
echo   Settings:  http://localhost:5173/settings
echo   API Docs:  http://localhost:8000/docs
echo.
echo   For Windows Service mode, run PowerShell as Admin:
echo   .\deploy-windows.ps1 -All
echo.
pause