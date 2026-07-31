$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

Write-Host "Building ArabicPyIDE.exe..." -ForegroundColor Cyan
python -m PyInstaller --noconfirm --clean ArabicPyIDE.spec

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

Write-Host "Updated: $projectRoot\dist\ArabicPyIDE\ArabicPyIDE.exe" -ForegroundColor Green
