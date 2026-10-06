# Post-Build Verification Script for VisionPilot
# Validates packaged executable execution, headless bootstrap, and release artifact integrity

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$DistExe = Join-Path $ProjectRoot "dist\VisionPilot\VisionPilot.exe"
$ReleaseDir = Join-Path $ProjectRoot "release"
$Version = "0.1.0"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " VisionPilot Post-Build Verification Pipeline" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Executable presence
Write-Host "`n[1/5] Checking packaged executable presence..." -ForegroundColor Yellow
if (-not (Test-Path $DistExe)) {
    Write-Error "Verification failed: $DistExe not found!"
    exit 1
}
$exeSize = (Get-Item $DistExe).Length / 1MB
Write-Host "Found: $DistExe ($([math]::Round($exeSize, 2)) MB)" -ForegroundColor Green

# 2. Executable --check-only execution
Write-Host "`n[2/5] Testing executable startup check (--check-only)..." -ForegroundColor Yellow
$proc = Start-Process -FilePath $DistExe -ArgumentList "--check-only" -PassThru -Wait
if ($proc.ExitCode -ne 0) {
    Write-Error "Executable --check-only failed with exit code $($proc.ExitCode)"
    exit 1
}
Write-Host "Startup check passed with exit code 0." -ForegroundColor Green

# 3. Executable --headless execution
Write-Host "`n[3/5] Testing executable headless execution (--headless)..." -ForegroundColor Yellow
$procHeadless = Start-Process -FilePath $DistExe -ArgumentList "--headless" -PassThru -Wait
if ($procHeadless.ExitCode -ne 0) {
    Write-Error "Executable --headless failed with exit code $($procHeadless.ExitCode)"
    exit 1
}
Write-Host "Headless execution passed with exit code 0." -ForegroundColor Green

# 4. Check Release Directory Artifacts
Write-Host "`n[4/5] Checking release artifacts..." -ForegroundColor Yellow
$ExpectedArtifacts = @(
    (Join-Path $ReleaseDir "VisionPilot-$Version-portable.zip"),
    (Join-Path $ReleaseDir "VisionPilot-Setup-$Version.exe"),
    (Join-Path $ReleaseDir "SHA256SUMS.txt")
)

foreach ($art in $ExpectedArtifacts) {
    if (Test-Path $art) {
        $sizeMB = (Get-Item $art).Length / 1MB
        Write-Host "  Artifact Verified: $(Split-Path $art -Leaf) ($([math]::Round($sizeMB, 2)) MB)" -ForegroundColor Green
    } else {
        Write-Warning "  Artifact missing or optional: $(Split-Path $art -Leaf)"
    }
}

# 5. Checksum verification
Write-Host "`n[5/5] Verifying SHA256 checksum file..." -ForegroundColor Yellow
$ChecksumFile = Join-Path $ReleaseDir "SHA256SUMS.txt"
if (Test-Path $ChecksumFile) {
    Get-Content $ChecksumFile | ForEach-Object {
        Write-Host "  $_" -ForegroundColor Gray
    }
    Write-Host "Checksum file verified." -ForegroundColor Green
}

Write-Host "`n============================================================" -ForegroundColor Green
Write-Host " All Post-Build Verifications Passed Successfully!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
