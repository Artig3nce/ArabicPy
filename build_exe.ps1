$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

if (-not (Test-Path -LiteralPath (Join-Path $projectRoot "vendor\llama.cpp\llama-server.exe"))) {
    & (Join-Path $projectRoot "prepare_embedded_ai.ps1")
}

Write-Host "Building AlBaa.exe..." -ForegroundColor Cyan
python -m PyInstaller --noconfirm --clean AlBaaIDE.spec

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

Write-Host "Updated: $projectRoot\dist\AlBaa\AlBaa.exe" -ForegroundColor Green
