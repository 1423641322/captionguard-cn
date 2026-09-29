$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PluginDirectory = Join-Path $ProjectRoot "plugin"
$OutputDirectory = Join-Path $ProjectRoot "dist\ccx"
$OutputFile = Join-Path $OutputDirectory "com.captionguard.cn_premierepro.ccx"
$StagingDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("captionguard-ccx-" + [guid]::NewGuid())

$PluginFiles = @(
    "manifest.json",
    "index.html",
    "index.js",
    "timeline.js",
    "styles.css"
)

try {
    New-Item -ItemType Directory -Path $StagingDirectory | Out-Null
    New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

    foreach ($File in $PluginFiles) {
        $Source = Join-Path $PluginDirectory $File
        if (-not (Test-Path -LiteralPath $Source)) {
            throw "Missing plugin file: $Source"
        }
        Copy-Item -LiteralPath $Source -Destination $StagingDirectory
    }

    if (Test-Path -LiteralPath $OutputFile) {
        Remove-Item -LiteralPath $OutputFile
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $StagingDirectory,
        $OutputFile,
        [System.IO.Compression.CompressionLevel]::Optimal,
        $false
    )
}
finally {
    if (Test-Path -LiteralPath $StagingDirectory) {
        Remove-Item -LiteralPath $StagingDirectory -Recurse -Force
    }
}

Write-Host "Built: $OutputFile"
