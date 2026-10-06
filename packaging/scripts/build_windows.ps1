# Production Windows Build Script for VisionPilot
# Packages VisionPilot into one-folder distribution, portable zip, and Inno Setup installer.

param (
    [switch]$SkipTests = $false,
    [string]$PythonExe = "C:\Users\rishi\AppData\Local\Python\pythoncore-3.14-64\python.exe"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$ReleaseDir = Join-Path $ProjectRoot "release"
$DistDir = Join-Path $ProjectRoot "dist\VisionPilot"
$Version = "0.1.0"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " VisionPilot Production Packaging Pipeline (v$Version)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Project Root: $ProjectRoot"
Write-Host "Python: $PythonExe"

# Step 1: Clean previous builds
Write-Host "`n[1/6] Cleaning prior build outputs..." -ForegroundColor Yellow
& (Join-Path $PSScriptRoot "clean_build.ps1")

# Step 2: Pre-build test verification
if (-not $SkipTests) {
    Write-Host "`n[2/6] Running pre-build regression and safety gates..." -ForegroundColor Yellow
    & $PythonExe -c "import pytest, os; rc = pytest.main(['tests/integration/test_security_adversarial.py', '-q']); os._exit(rc)"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Pre-build safety validation failed! Aborting packaging."
        exit 1
    }
    & $PythonExe -c "import pytest, os; rc = pytest.main(['tests/unit/test_foundation.py', '-q']); os._exit(rc)"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Pre-build foundation tests failed! Aborting packaging."
        exit 1
    }
    Write-Host "Pre-build gates passed successfully." -ForegroundColor Green
} else {
    Write-Host "`n[2/6] Skipping pre-build tests (-SkipTests requested)." -ForegroundColor Gray
}

# Step 3: Run PyInstaller
Write-Host "`n[3/6] Running PyInstaller packaging..." -ForegroundColor Yellow
$SpecFile = Join-Path $ProjectRoot "packaging\pyinstaller\VisionPilot.spec"
$distPath = Join-Path $ProjectRoot "dist"
$workPath = Join-Path $ProjectRoot "build"
$pyiProc = Start-Process -FilePath $PythonExe -ArgumentList "-m", "PyInstaller", "--clean", "--noconfirm", "--distpath", "`"$distPath`"", "--workpath", "`"$workPath`"", "`"$SpecFile`"" -NoNewWindow -PassThru -Wait
if ($pyiProc.ExitCode -ne 0) {
    Write-Error "PyInstaller packaging failed with exit code $($pyiProc.ExitCode)!"
    exit 1
}

$Executable = Join-Path $DistDir "VisionPilot.exe"
if (-not (Test-Path $Executable)) {
    Write-Error "Packaging failed: $Executable does not exist!"
    exit 1
}
Write-Host "Executable generated: $Executable" -ForegroundColor Green

# Ensure release directory exists
if (-not (Test-Path $ReleaseDir)) {
    New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null
}

# Step 4: Create Portable ZIP Archive
Write-Host "`n[4/6] Creating Portable ZIP distribution..." -ForegroundColor Yellow
$PortableZip = Join-Path $ReleaseDir "VisionPilot-$Version-portable.zip"
if (Test-Path $PortableZip) { Remove-Item $PortableZip -Force }

# Add portable marker file into dist/VisionPilot
Set-Content -Path (Join-Path $DistDir "portable.txt") -Value "VISIONPILOT_PORTABLE_MODE=1" -Encoding UTF8

Compress-Archive -Path "$DistDir\*" -DestinationPath $PortableZip -CompressionLevel Optimal
Write-Host "Portable archive created: $PortableZip" -ForegroundColor Green

# Remove portable marker from dist so installer gets clean standard mode
Remove-Item (Join-Path $DistDir "portable.txt") -Force -ErrorAction SilentlyContinue

# Step 5: Compile Windows Installer via Inno Setup
Write-Host "`n[5/6] Compiling Windows Installer with Inno Setup..." -ForegroundColor Yellow
$IsccCandidates = @(
    "C:\Users\rishi\AppData\Local\Programs\Antigravity IDE\resources\app\node_modules\innosetup\bin\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)

$IsccExe = $null
foreach ($cand in $IsccCandidates) {
    if (Test-Path $cand) {
        $IsccExe = $cand
        break
    }
}

if ($IsccExe) {
    Write-Host "Using Inno Setup compiler: $IsccExe"
    $IssScript = Join-Path $ProjectRoot "packaging\installer\VisionPilot.iss"
    & "$IsccExe" "$IssScript"
    $SetupExe = Join-Path $ReleaseDir "VisionPilot-Setup-$Version.exe"
    if (Test-Path $SetupExe) {
        Write-Host "Installer generated successfully: $SetupExe" -ForegroundColor Green
    } else {
        Write-Warning "Inno Setup ran but $SetupExe was not found."
    }
} else {
    Write-Warning "Inno Setup compiler (ISCC.exe) not found. Skipped installer compilation."
}

# Step 6: Generate SHA-256 Checksums
Write-Host "`n[6/6] Generating SHA-256 Checksums..." -ForegroundColor Yellow
$ChecksumFile = Join-Path $ReleaseDir "SHA256SUMS.txt"
$ReleaseFiles = Get-ChildItem -Path $ReleaseDir -File | Where-Object { $_.Name -ne "SHA256SUMS.txt" -and $_.Name -ne "RELEASE_NOTES.md" }

$ChecksumLines = @()
foreach ($file in $ReleaseFiles) {
    $hash = (Get-FileHash -Path $file.FullName -Algorithm SHA256).Hash.ToLower()
    $ChecksumLines += "$hash  $($file.Name)"
    Write-Host "  $($file.Name): $hash"
}

$ChecksumLines | Out-File -FilePath $ChecksumFile -Encoding UTF8 -Force
Write-Host "Checksums written to: $ChecksumFile" -ForegroundColor Green

Write-Host "`n============================================================" -ForegroundColor Green
Write-Host " Phase 12 Build Complete! Artifacts in: $ReleaseDir" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
