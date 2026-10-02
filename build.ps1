param(
    [string]$Python = ".\.venv\Scripts\python.exe",
    [string]$Version = "0.2.0",
    [switch]$SkipBundle,
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$pythonCommand = Get-Command $Python -ErrorAction SilentlyContinue
if (-not $pythonCommand) { throw "Python not found: $Python. Create .venv and install requirements-build.txt first." }
$Python = $pythonCommand.Source

if (-not $SkipBundle) {
    & $Python -m pip install -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw 'Could not install build dependencies.' }

    & $Python -m PyInstaller --noconfirm --clean --windowed --onedir `
        --name VoiceInput `
        --distpath .\dist `
        --workpath .\build\pyinstaller `
        --collect-all faster_whisper `
        --collect-all ctranslate2 `
        --collect-all av `
        --collect-all sounddevice `
        --collect-all pystray `
        --collect-all PIL `
        --collect-all huggingface_hub `
        --collect-data certifi `
        .\tray_app.py
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
}

$exe = Join-Path $root 'dist\VoiceInput\VoiceInput.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw "Build output missing: $exe" }

if (-not $SkipInstaller) {
    $candidatePaths = @(
        (Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1),
        "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )
    $compiler = $candidatePaths | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
    if (-not $compiler) {
        Write-Warning 'Inno Setup 6 was not found. App files were built in dist\VoiceInput; install Inno Setup 6 and rerun to create the installer.'
        exit 0
    }
    & $compiler "/DAppVersion=$Version" '.\installer\VoiceInput.iss'
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup compilation failed.' }
    $installer = Join-Path $root "build\installer\VoiceInput-Setup-$Version-x64.exe"
    $hash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -LiteralPath "${installer}.sha256" -Value "$hash  $(Split-Path -Leaf $installer)" -Encoding ascii
}
