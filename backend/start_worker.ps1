# PowerShell script to start the worker process

Write-Host "Starting worker process..." -ForegroundColor Cyan
Write-Host ""

# Change to backend directory
Set-Location $PSScriptRoot

# Activate virtual environment if it exists
if (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & "venv\Scripts\Activate.ps1"
}

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Host "[WARNING] .env file not found. Make sure database credentials are set!" -ForegroundColor Yellow
    Write-Host ""
}

# Start worker
Write-Host "Starting job processor worker..." -ForegroundColor Green
Write-Host "Worker will process queued jobs from the database" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the worker" -ForegroundColor Yellow
Write-Host ""

python -m app.workers.job_processor

