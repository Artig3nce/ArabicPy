$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

Write-Host "Building AlBaa.exe..." -ForegroundColor Cyan
python -m PyInstaller --noconfirm --clean AlBaaIDE.spec

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

Write-Host "Updated: $projectRoot\dist\AlBaa\AlBaa.exe" -ForegroundColor Green
