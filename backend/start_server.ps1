# PowerShell script to start the FastAPI development server

Write-Host "Starting FastAPI development server..." -ForegroundColor Cyan
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

# Start uvicorn server
Write-Host "Starting server on http://localhost:8000" -ForegroundColor Green
Write-Host "API docs will be available at http://localhost:8000/api/docs" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

