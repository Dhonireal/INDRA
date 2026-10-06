# Safe Build Cleaner for VisionPilot
# Removes temporary build, dist, and pyinstaller artifacts without touching user data

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")

Write-Host "Cleaning VisionPilot build artifacts in $ProjectRoot..." -ForegroundColor Cyan

$Targets = @(
    (Join-Path $ProjectRoot "build"),
    (Join-Path $ProjectRoot "dist"),
    (Join-Path $ProjectRoot "__pycache__")
)

foreach ($Target in $Targets) {
    if (Test-Path $Target) {
        Write-Host "Removing $Target..." -ForegroundColor Yellow
        Remove-Item -Path $Target -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# Clean Python caches in app/
Get-ChildItem -Path (Join-Path $ProjectRoot "app") -Recurse -Filter "__pycache__" -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -Path $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Clean complete." -ForegroundColor Green
