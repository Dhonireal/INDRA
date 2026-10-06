# Deterministic Demo Environment Reset Script for VisionPilot
# Safely recreates the isolated demo workspace (VisionPilot-Demo/) without touching real user folders

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$DemoDir = Join-Path $ProjectRoot "VisionPilot-Demo"
$DownloadsDir = Join-Path $DemoDir "Downloads"
$ResearchDir = Join-Path $DemoDir "Research"

Write-Host "Resetting VisionPilot demo environment at: $DemoDir" -ForegroundColor Cyan

# Remove old demo workspace safely
if (Test-Path $DemoDir) {
    Remove-Item -Path $DemoDir -Recurse -Force
}

# Recreate folders
New-Item -ItemType Directory -Path $DownloadsDir -Force | Out-Null
New-Item -ItemType Directory -Path $ResearchDir -Force | Out-Null

# Populate sample demonstration PDF files with synthetic content
$SamplePdf1 = Join-Path $DownloadsDir "Qualcomm-AI-Research.pdf"
$SamplePdf2 = Join-Path $DownloadsDir "AI-Notes.pdf"
$SamplePdf3 = Join-Path $DownloadsDir "VisionPilot-Architecture.pdf"

Set-Content -Path $SamplePdf1 -Value "%PDF-1.4 Demonstration sample for Snapdragon AI PC computer-use." -Encoding UTF8
Set-Content -Path $SamplePdf2 -Value "%PDF-1.4 AI Agent Design and Safety Verification Notes." -Encoding UTF8
Set-Content -Path $SamplePdf3 -Value "%PDF-1.4 VisionPilot Technical Specification and Architecture." -Encoding UTF8

Write-Host "Demo environment successfully initialized:" -ForegroundColor Green
Write-Host "  - Downloads: $(Get-ChildItem -Path $DownloadsDir | Measure-Object | Select-Object -ExpandProperty Count) files"
Write-Host "  - Research: $(Get-ChildItem -Path $ResearchDir | Measure-Object | Select-Object -ExpandProperty Count) files"
