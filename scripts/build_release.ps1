$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot

& (Join-Path $PSScriptRoot "build_ccx.ps1")
& (Join-Path $PSScriptRoot "build_windows.ps1")

Write-Host "Release ready: $(Join-Path $ProjectRoot 'dist\CaptionGuard-CN.exe')"
