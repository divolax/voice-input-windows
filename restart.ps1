$ErrorActionPreference = 'Stop'

$folder = $PSScriptRoot
$processes = Get-CimInstance -ClassName Win32_Process -Filter "Name = 'python.exe'" |
    Where-Object {
        $_.CommandLine -and
        $_.CommandLine.IndexOf($folder, [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $_.CommandLine -match '(?i)dictation\.py'
    }

foreach ($process in $processes) {
    Stop-Process -Id $process.ProcessId -Force
    Wait-Process -Id $process.ProcessId -Timeout 10 -ErrorAction SilentlyContinue
}

$stillRunning = Get-CimInstance -ClassName Win32_Process -Filter "Name = 'python.exe'" |
    Where-Object {
        $_.CommandLine -and
        $_.CommandLine.IndexOf($folder, [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $_.CommandLine -match '(?i)dictation\.py'
    }
if ($stillRunning) {
    throw 'The existing voice input process did not stop; refusing to start a duplicate.'
}

$launcher = Join-Path $folder 'start-or-focus.vbs'
Start-Process -FilePath (Join-Path $env:SystemRoot 'System32\wscript.exe') `
    -ArgumentList ('"' + $launcher + '"') `
    -WorkingDirectory $folder `
    -WindowStyle Hidden
