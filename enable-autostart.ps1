$ErrorActionPreference = 'Stop'
$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
$script = Join-Path $PSScriptRoot 'tray_app.py'
if (-not (Test-Path -LiteralPath $python)) { throw 'Сначала запустите .\install.ps1' }
$command = '"{0}" "{1}"' -f $python, $script
$key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
New-Item -Path $key -Force | Out-Null
Set-ItemProperty -Path $key -Name 'Voice Input' -Value $command
Write-Host 'Автозапуск Voice Input включён.'
Write-Host 'Войдёт в силу при следующем входе в Windows.'
