$ErrorActionPreference = 'Stop'
$key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
if (Get-ItemProperty -Path $key -Name 'Voice Input' -ErrorAction SilentlyContinue) {
    Remove-ItemProperty -Path $key -Name 'Voice Input' -Force
    Write-Host 'Автозапуск выключен.'
} else {
    Write-Host 'Автозапуск уже не был включён.'
}
