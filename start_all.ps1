# PowerShell script to start all DocData SaaS services
# This script starts: Backend Server, Worker, Main App, Admin Frontend, and Marketing Site

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  DocData SaaS - Starting All Services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get the script directory (docdata_saas root)
$RootDir = $PSScriptRoot
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"
$AdminFrontendDir = Join-Path $RootDir "admin_frontend"
$MarketingSiteDir = Join-Path $RootDir "marketing_site"

# Check if directories exist
$Directories = @(
    @{Name="Backend"; Path=$BackendDir},
    @{Name="Frontend"; Path=$FrontendDir},
    @{Name="Admin Frontend"; Path=$AdminFrontendDir},
    @{Name="Marketing Site"; Path=$MarketingSiteDir}
)

foreach ($Dir in $Directories) {
    if (-not (Test-Path $Dir.Path)) {
        Write-Host "[ERROR] $($Dir.Name) directory not found: $($Dir.Path)" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Starting services in separate windows..." -ForegroundColor Yellow
Write-Host ""

# Start Backend Server
Write-Host "[1/5] Starting Backend Server (port 8000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$BackendDir'; .\start_server.ps1" -WindowStyle Normal

# Wait a moment before starting next service
Start-Sleep -Seconds 2

# Start Worker
Write-Host "[2/5] Starting Worker..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$BackendDir'; .\start_worker.ps1" -WindowStyle Normal

# Wait a moment before starting next service
Start-Sleep -Seconds 2

# Start Main Frontend App
Write-Host "[3/5] Starting Main App Frontend (port 3000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$FrontendDir'; npm run dev" -WindowStyle Normal

# Wait a moment before starting next service
Start-Sleep -Seconds 2

# Start Admin Frontend
Write-Host "[4/5] Starting Admin Frontend (port 3001)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$AdminFrontendDir'; npm run dev" -WindowStyle Normal

# Wait a moment before starting next service
Start-Sleep -Seconds 2

# Start Marketing Site
Write-Host "[5/5] Starting Marketing Site (port 4321)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$MarketingSiteDir'; npm run dev" -WindowStyle Normal

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  All services are starting!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services will be available at:" -ForegroundColor Yellow
Write-Host "  - Backend API:      http://localhost:8000" -ForegroundColor White
Write-Host "  - API Docs:         http://localhost:8000/api/docs" -ForegroundColor White
Write-Host "  - Main App:         http://localhost:3000" -ForegroundColor White
Write-Host "  - Admin Frontend:   http://localhost:3001" -ForegroundColor White
Write-Host "  - Marketing Site:   http://localhost:4321" -ForegroundColor White
Write-Host ""
Write-Host "Each service is running in its own window." -ForegroundColor Yellow
Write-Host "Close the windows or press Ctrl+C in each window to stop the services." -ForegroundColor Yellow
Write-Host ""
