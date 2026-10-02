$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    Write-Host 'Сначала запустите .\install.ps1' -ForegroundColor Yellow
    exit 1
}
& '.\.venv\Scripts\python.exe' .\tray_app.py
