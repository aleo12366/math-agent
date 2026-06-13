# ============================================================
# Math Agent System - Windows Server Deployment Script
# ============================================================
# Usage: .\deploy-windows.ps1 [-InstallNginx] [-BuildFrontend] [-StartServices]
# ============================================================

param(
    [switch]$InstallNginx,
    [switch]$BuildFrontend,
    [switch]$StartServices,
    [switch]$StopServices,
    [switch]$InstallNSSM,
    [switch]$SetupServices,
    [switch]$All
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$DeployDir = Join-Path $ProjectRoot "deploy"
$NginxDir = "C:\nginx-mathagent"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Math Agent System - Windows Deploy" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================
# Step 1: Build Frontend
# ============================================================
function Build-Frontend {
    Write-Host "[1/5] Building frontend..." -ForegroundColor Yellow

    Push-Location $FrontendDir
    try {
        Write-Host "  Installing npm packages..."
        npm install --production=false 2>&1 | Out-Null

        Write-Host "  Building production bundle..."
        npm run build 2>&1 | Out-Null

        # Copy build output to deploy directory
        $distDir = Join-Path $FrontendDir "dist"
        $htmlDir = Join-Path $DeployDir "html"

        if (Test-Path $htmlDir) {
            Remove-Item -Recurse -Force $htmlDir
        }
        Copy-Item -Recurse -Force $distDir $htmlDir

        Write-Host "  Frontend built successfully!" -ForegroundColor Green
    }
    finally {
        Pop-Location
    }
}

# ============================================================
# Step 2: Install Nginx
# ============================================================
function Install-Nginx {
    Write-Host "[2/5] Setting up Nginx..." -ForegroundColor Yellow

    # Download nginx for Windows
    $nginxUrl = "https://nginx.org/download/nginx-1.27.4.zip"
    $nginxZip = Join-Path $env:TEMP "nginx-win.zip"

    if (-not (Test-Path $NginxDir)) {
        Write-Host "  Downloading Nginx..."
        Invoke-WebRequest -Uri $nginxUrl -OutFile $nginxZip -UseBasicParsing

        Write-Host "  Extracting Nginx..."
        Expand-Archive -Path $nginxZip -DestinationPath $env:TEMP -Force
        $extractedDir = Get-ChildItem -Path $env:TEMP -Directory | Where-Object { $_.Name -like "nginx-*" } | Select-Object -First 1
        Move-Item (Join-Path $env:TEMP $extractedDir.Name) $NginxDir

        Remove-Item $nginxZip -ErrorAction SilentlyContinue
        Write-Host "  Nginx installed to $NginxDir" -ForegroundColor Green
    }
    else {
        Write-Host "  Nginx already installed at $NginxDir" -ForegroundColor Green
    }

    # Copy config
    $confSrc = Join-Path $ProjectRoot "nginx-windows.conf"
    $confDst = Join-Path $NginxDir "conf\nginx.conf"

    if (Test-Path $confSrc) {
        Copy-Item -Force $confSrc $confDst
        Write-Host "  Nginx config updated" -ForegroundColor Green
    }

    # Copy frontend build to nginx html
    $htmlSrc = Join-Path $DeployDir "html"
    $htmlDst = Join-Path $NginxDir "html"

    if (Test-Path $htmlSrc) {
        if (Test-Path $htmlDst) {
            Remove-Item -Recurse -Force $htmlDst
        }
        Copy-Item -Recurse -Force $htmlSrc $htmlDst
        Write-Host "  Frontend files copied to Nginx" -ForegroundColor Green
    }
    else {
        Write-Host "  WARNING: No frontend build found. Run with -BuildFrontend first." -ForegroundColor Red
    }
}

# ============================================================
# Step 3: Setup Python Backend
# ============================================================
function Setup-Backend {
    Write-Host "[3/5] Setting up backend..." -ForegroundColor Yellow

    Push-Location $BackendDir
    try {
        # Create virtual environment if not exists
        $venvDir = Join-Path $BackendDir "venv"
        if (-not (Test-Path $venvDir)) {
            Write-Host "  Creating Python virtual environment..."
            python -m venv venv
        }

        # Activate and install
        $pipExe = Join-Path $venvDir "Scripts\pip.exe"
        $pythonExe = Join-Path $venvDir "Scripts\python.exe"

        Write-Host "  Upgrading pip..."
        & $pythonExe -m pip install --upgrade pip setuptools wheel 2>&1 | Out-Null

        Write-Host "  Installing Python packages..."
        & $pipExe install -r requirements.txt 2>&1 | Out-Null

        # Create .env if not exists
        $envFile = Join-Path $BackendDir ".env"
        $envExample = Join-Path $BackendDir ".env.example"
        if (-not (Test-Path $envFile) -and (Test-Path $envExample)) {
            Copy-Item $envExample $envFile
            Write-Host "  Created .env from .env.example" -ForegroundColor Yellow
            Write-Host "  IMPORTANT: Edit .env file with your API key!" -ForegroundColor Red
        }

        Write-Host "  Backend setup complete!" -ForegroundColor Green
    }
    finally {
        Pop-Location
    }
}

# ============================================================
# Step 4: Install NSSM (Non-Sucking Service Manager)
# ============================================================
function Install-NSSM {
    Write-Host "[4/5] Setting up NSSM for Windows services..." -ForegroundColor Yellow

    $nssmDir = "C:\nssm"
    $nssmExe = Join-Path $nssmDir "win64\nssm.exe"

    if (-not (Test-Path $nssmExe)) {
        $nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
        $nssmZip = Join-Path $env:TEMP "nssm.zip"

        Write-Host "  Downloading NSSM..."
        Invoke-WebRequest -Uri $nssmUrl -OutFile $nssmZip -UseBasicParsing

        Write-Host "  Extracting NSSM..."
        Expand-Archive -Path $nssmZip -DestinationPath $env:TEMP -Force
        $extractedDir = Get-ChildItem -Path $env:TEMP -Directory | Where-Object { $_.Name -like "nssm-*" } | Select-Object -First 1
        Move-Item (Join-Path $env:TEMP $extractedDir.Name) $nssmDir

        Remove-Item $nssmZip -ErrorAction SilentlyContinue
        Write-Host "  NSSM installed to $nssmDir" -ForegroundColor Green
    }
    else {
        Write-Host "  NSSM already installed" -ForegroundColor Green
    }
}

# ============================================================
# Step 5: Setup Windows Services
# ============================================================
function Setup-Services {
    Write-Host "[5/5] Configuring Windows services..." -ForegroundColor Yellow

    $nssmExe = "C:\nssm\win64\nssm.exe"
    $pythonExe = Join-Path $BackendDir "venv\Scripts\python.exe"
    $mainPy = Join-Path $BackendDir "main.py"
    $nginxExe = Join-Path $NginxDir "nginx.exe"

    # Backend service
    Write-Host "  Installing MathAgentBackend service..."
    & $nssmExe stop MathAgentBackend 2>&1 | Out-Null
    & $nssmExe remove MathAgentBackend confirm 2>&1 | Out-Null
    & $nssmExe install MathAgentBackend $pythonExe
    & $nssmExe set MathAgentBackend AppParameters "`"$mainPy`""
    & $nssmExe set MathAgentBackend AppDirectory $BackendDir
    & $nssmExe set MathAgentBackend DisplayName "Math Agent Backend"
    & $nssmExe set MathAgentBackend Description "Math Agent System - Python FastAPI Backend"
    & $nssmExe set MathAgentBackend Start SERVICE_AUTO_START
    & $nssmExe set MathAgentBackend AppStdout (Join-Path $BackendDir "logs\backend-stdout.log")
    & $nssmExe set MathAgentBackend AppStderr (Join-Path $BackendDir "logs\backend-stderr.log")
    & $nssmExe set MathAgentBackend AppRotateFiles 1
    & $nssmExe set MathAgentBackend AppRotateBytes 10485760

    # Create logs directory
    $logsDir = Join-Path $BackendDir "logs"
    if (-not (Test-Path $logsDir)) {
        New-Item -ItemType Directory -Path $logsDir | Out-Null
    }

    Write-Host "  MathAgentBackend service installed" -ForegroundColor Green

    # Nginx service
    Write-Host "  Installing MathAgentNginx service..."
    & $nssmExe stop MathAgentNginx 2>&1 | Out-Null
    & $nssmExe remove MathAgentNginx confirm 2>&1 | Out-Null
    & $nssmExe install MathAgentNginx $nginxExe
    & $nssmExe set MathAgentNginx AppParameters ""
    & $nssmExe set MathAgentNginx AppDirectory $NginxDir
    & $nssmExe set MathAgentNginx DisplayName "Math Agent Nginx"
    & $nssmExe set MathAgentNginx Description "Math Agent System - Nginx Reverse Proxy"
    & $nssmExe set MathAgentNginx Start SERVICE_AUTO_START

    Write-Host "  MathAgentNginx service installed" -ForegroundColor Green
}

# ============================================================
# Start Services
# ============================================================
function Start-Services {
    Write-Host "Starting services..." -ForegroundColor Yellow

    # Start backend
    Write-Host "  Starting backend service..."
    Start-Service MathAgentBackend -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2

    # Start nginx
    Write-Host "  Starting Nginx service..."
    Start-Service MathAgentNginx -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Services started!" -ForegroundColor Green
    Write-Host "  Frontend: http://localhost" -ForegroundColor Green
    Write-Host "  Backend:  http://localhost:8000" -ForegroundColor Green
    Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
}

# ============================================================
# Stop Services
# ============================================================
function Stop-Services {
    Write-Host "Stopping services..." -ForegroundColor Yellow

    Stop-Service MathAgentNginx -ErrorAction SilentlyContinue
    Stop-Service MathAgentBackend -ErrorAction SilentlyContinue

    Write-Host "  All services stopped" -ForegroundColor Green
}

# ============================================================
# Main execution
# ============================================================
if ($All) {
    $InstallNginx = $true
    $BuildFrontend = $true
    $SetupServices = $true
    $StartServices = $true
}

if ($InstallNginx) { Install-Nginx }
if ($BuildFrontend) { Build-Frontend }
if ($InstallNSSM) { Install-NSSM }

# Always setup backend
Setup-Backend

if ($SetupServices) { Install-NSSM; Setup-Services }
if ($StopServices) { Stop-Services }
if ($StartServices) { Start-Services }

# If no switches provided, show help
if (-not ($InstallNginx -or $BuildFrontend -or $StartServices -or $StopServices -or $InstallNSSM -or $SetupServices -or $All)) {
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\deploy-windows.ps1 -All              # Full deployment (build + install + start)"
    Write-Host "  .\deploy-windows.ps1 -BuildFrontend     # Build frontend only"
    Write-Host "  .\deploy-windows.ps1 -InstallNginx      # Install/configure Nginx"
    Write-Host "  .\deploy-windows.ps1 -SetupServices     # Install Windows services"
    Write-Host "  .\deploy-windows.ps1 -StartServices     # Start all services"
    Write-Host "  .\deploy-windows.ps1 -StopServices      # Stop all services"
    Write-Host ""
    Write-Host "First-time setup:" -ForegroundColor Cyan
    Write-Host "  1. Edit backend\.env with your API key"
    Write-Host "  2. Run: .\deploy-windows.ps1 -All"
    Write-Host "  3. Open http://localhost"
    Write-Host ""
}