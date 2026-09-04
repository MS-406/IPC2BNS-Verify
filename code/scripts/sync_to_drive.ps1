# sync_to_drive.ps1 — Synchronize local NLP_rs to Google Drive NLP_rspaper

$localDir = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$driveDir = "G:\My Drive\NLP_rspaper"

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "IPC2BNS-Verify: Google Drive Synchronization Tool" -ForegroundColor Cyan
Write-Host "Local : $localDir"
Write-Host "Target: $driveDir"
Write-Host "======================================================================" -ForegroundColor Cyan

if (-not (Test-Path $driveDir)) {
    Write-Host "[ERROR] Google Drive path not found at: $driveDir" -ForegroundColor Red
    Write-Host "Please ensure Google Drive for Desktop is running and signed in." -ForegroundColor Yellow
    exit 1
}

Write-Host "Synchronizing files with Robocopy..." -ForegroundColor Green
$excludeDirs = @(".git", ".pytest_cache", ".qodo", "__pycache__")
$excludeFiles = @("*.tmp", "*.log")

robocopy "$localDir" "$driveDir" /MIR /XD $excludeDirs /XF $excludeFiles

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "[SUCCESS] Synchronization to Google Drive completed successfully!" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Cyan
