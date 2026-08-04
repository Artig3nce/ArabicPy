$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$engineDir = Join-Path $projectRoot "vendor\llama.cpp"
$serverPath = Join-Path $engineDir "llama-server.exe"

if (Test-Path -LiteralPath $serverPath -PathType Leaf) {
    Write-Host "Embedded llama.cpp is already prepared." -ForegroundColor Green
    exit 0
}

New-Item -ItemType Directory -Force -Path $engineDir | Out-Null
$apiHeaders = @{ "User-Agent" = "AlBaa-Build" }
if ($env:GITHUB_TOKEN) {
    $apiHeaders["Authorization"] = "Bearer $($env:GITHUB_TOKEN)"
}
$release = Invoke-RestMethod -Uri "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest" -Headers $apiHeaders
$asset = $release.assets | Where-Object { $_.name -match 'bin-win-cpu-x64\.zip$' } | Select-Object -First 1
if (-not $asset) {
    throw "The official llama.cpp Windows CPU package was not found in the latest release."
}

$archive = Join-Path $env:TEMP $asset.name
Write-Host "Downloading official llama.cpp $($release.tag_name)..." -ForegroundColor Cyan
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $archive
Expand-Archive -LiteralPath $archive -DestinationPath $engineDir -Force

$foundServer = Get-ChildItem -LiteralPath $engineDir -Filter "llama-server.exe" -File -Recurse | Select-Object -First 1
if (-not $foundServer) {
    throw "llama-server.exe was not present in the downloaded official package."
}
if ($foundServer.Directory.FullName -ne $engineDir) {
    Get-ChildItem -LiteralPath $foundServer.Directory.FullName -File | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $engineDir $_.Name) -Force
    }
}
Write-Host "Embedded AI engine prepared: $serverPath" -ForegroundColor Green
