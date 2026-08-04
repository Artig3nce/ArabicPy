$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

Write-Host "Building AlBaa.exe..." -ForegroundColor Cyan
python assets\generate_icon.py
if ($LASTEXITCODE -ne 0) {
    throw "Icon generation failed with exit code $LASTEXITCODE."
}
python -m PyInstaller --noconfirm --clean --distpath dist AlBaaAIHost.spec
if ($LASTEXITCODE -ne 0) {
    throw "AI host build failed with exit code $LASTEXITCODE."
}
python -m PyInstaller --noconfirm --clean AlBaaIDE.spec

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

Write-Host "Updated: $projectRoot\dist\AlBaa\AlBaa.exe" -ForegroundColor Green
