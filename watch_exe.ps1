$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$buildScript = Join-Path $projectRoot "build_exe.ps1"
$watchedPaths = @(
    (Join-Path $projectRoot "arabicpy")
    (Join-Path $projectRoot "launch_ide.py")
    (Join-Path $projectRoot "main.py")
    (Join-Path $projectRoot "ArabicPyIDE.spec")
)

function Get-SourceState {
    $files = foreach ($path in $watchedPaths) {
        if (Test-Path $path -PathType Container) {
            Get-ChildItem -Path $path -Recurse -File -Include *.py
        }
        elseif (Test-Path $path -PathType Leaf) {
            Get-Item $path
        }
    }

    return ($files |
        Sort-Object FullName |
        ForEach-Object { "$($_.FullName)|$($_.LastWriteTimeUtc.Ticks)|$($_.Length)" }) -join "`n"
}

Write-Host "Watching ArabicPy source files. Press Ctrl+C to stop." -ForegroundColor Cyan
Write-Host "Close ArabicPyIDE.exe before saving so Windows can replace it." -ForegroundColor Yellow

$previousState = Get-SourceState

while ($true) {
    Start-Sleep -Milliseconds 750
    $currentState = Get-SourceState

    if ($currentState -ne $previousState) {
        $previousState = $currentState
        Write-Host "`nChange detected at $(Get-Date -Format T). Rebuilding..." -ForegroundColor Cyan

        try {
            & $buildScript
        }
        catch {
            Write-Host $_ -ForegroundColor Red
            Write-Host "Fix the error and save again to retry." -ForegroundColor Yellow
        }

        # Capture files generated or touched while the build was running.
        $previousState = Get-SourceState
    }
}
