# Start the backend server using the venv's Python
# This ensures chromadb and all other venv packages are found
$VenvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-Not (Test-Path $VenvPython)) {
    Write-Host "ERROR: Virtual environment not found at .venv\" -ForegroundColor Red
    Write-Host "Create it with: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

Write-Host "Using Python: $VenvPython" -ForegroundColor Green
& $VenvPython -m uvicorn server:app --host 0.0.0.0 --port 8001
