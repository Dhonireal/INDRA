# Flagship Demonstration Runner for VisionPilot
# Prepares the isolated demo environment and launches the packaged VisionPilot application

param (
    [switch]$UsePackaged = $true
)

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$DistExe = Join-Path $ProjectRoot "dist\VisionPilot\VisionPilot.exe"
$PythonExe = "C:\Users\rishi\AppData\Local\Python\pythoncore-3.14-64\python.exe"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " VisionPilot Flagship Demonstration Launch" -ForegroundColor Cyan
Write-Host " Tagline: 'See. Understand. Act. Verify.'" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Reset demo environment
& (Join-Path $PSScriptRoot "reset_demo_environment.ps1")

# 2. Display demo script guidance
Write-Host "`n--- FLAGSHIP DEMONSTRATION WORKFLOW ---" -ForegroundColor Yellow
Write-Host "Command to submit in VisionPilot:" -ForegroundColor White
Write-Host "  'Find the latest PDF in Downloads, rename it to Qualcomm-AI.pdf, move it to my Research folder, and verify the result.'" -ForegroundColor Green
Write-Host "`nExpected Agent Execution Pipeline:" -ForegroundColor White
Write-Host "  1. Understand  -> Parse command and validate parameters"
Write-Host "  2. Perceive    -> Locate latest PDF in demo Downloads"
Write-Host "  3. Plan        -> Decompose into FIND -> RENAME -> MOVE -> VERIFY"
Write-Host "  4. Safety      -> Evaluate risk (LOW) within allowed workspace"
Write-Host "  5. Act         -> Execute rename and move file operations"
Write-Host "  6. Verify      -> Confirm Qualcomm-AI.pdf in Research & original absent"
Write-Host "  7. Persist     -> Record audit trail & state in SQLite history"
Write-Host "---------------------------------------`n" -ForegroundColor Yellow

# 3. Launch application
if ($UsePackaged -and (Test-Path $DistExe)) {
    Write-Host "Launching packaged production build: $DistExe" -ForegroundColor Cyan
    Start-Process -FilePath $DistExe
} else {
    Write-Host "Launching development application via Python..." -ForegroundColor Cyan
    $MainPy = Join-Path $ProjectRoot "app\main.py"
    Start-Process -FilePath $PythonExe -ArgumentList "$MainPy"
}

Write-Host "VisionPilot is now active. Follow the steps in docs/demo-script.md for presentation." -ForegroundColor Green
