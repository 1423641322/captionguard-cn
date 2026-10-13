$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$CcxDirectory = Join-Path $ProjectRoot "dist\ccx"
$BuildRoot = Join-Path $ProjectRoot "build\portable"
$PayloadRoot = Join-Path $BuildRoot "payload"
$PythonTarget = Join-Path $PayloadRoot "python"
$PayloadArchive = Join-Path $BuildRoot "payload.zip"
$OutputFile = Join-Path $ProjectRoot "dist\CaptionGuard-CN.exe"
$IconFile = Join-Path $ProjectRoot "assets\captionguard.ico"
$Compiler = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
$env:PYTHONNOUSERSITE = "1"

if (-not (Get-ChildItem $CcxDirectory -Filter *.ccx -ErrorAction SilentlyContinue)) {
    throw "Missing dist\ccx\*.ccx. Build the UXP plugin first."
}
if (-not (Test-Path -LiteralPath $Compiler)) {
    throw "The Windows .NET Framework C# compiler was not found."
}
if (-not (Test-Path -LiteralPath $IconFile)) {
    throw "Missing Windows application icon: $IconFile"
}

$BuildPython = & (Join-Path $PSScriptRoot "prepare_build_python.ps1") | Select-Object -Last 1
if (-not (Test-Path -LiteralPath $BuildPython)) {
    throw "Python 3.12 build environment was not created."
}
$BuildPythonDirectory = Split-Path -Parent $BuildPython

$ResolvedProject = [System.IO.Path]::GetFullPath($ProjectRoot)
$ResolvedBuild = [System.IO.Path]::GetFullPath($BuildRoot)
if (-not $ResolvedBuild.StartsWith($ResolvedProject + [System.IO.Path]::DirectorySeparatorChar)) {
    throw "Refusing to clean a build directory outside the project."
}
if (Test-Path -LiteralPath $BuildRoot) {
    Remove-Item -LiteralPath $BuildRoot -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $PythonTarget | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $PayloadRoot "backend") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $PayloadRoot "plugin") | Out-Null

foreach ($Pattern in @("*.dll", "*.pyd", "python.exe", "pythonw.exe", "python312.zip", "LICENSE.txt")) {
    Copy-Item -Path (Join-Path $BuildPythonDirectory $Pattern) -Destination $PythonTarget
}

$RuntimeRequirements = @(
    "fastapi>=0.115,<1",
    "pydantic>=2.9,<3",
    "python-multipart>=0.0.12,<1",
    "uvicorn[standard]>=0.32,<1",
    "faster-whisper>=1.1,<2",
    "pillow>=11,<13",
    "pystray>=0.19,<1"
)
& $BuildPython -m pip install `
    --no-warn-script-location `
    $RuntimeRequirements
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install runtime dependencies."
}

$SitePackages = Join-Path $PythonTarget "Lib\site-packages"
New-Item -ItemType Directory -Force -Path $SitePackages | Out-Null
Copy-Item -Path (Join-Path $BuildPythonDirectory "Lib\site-packages\*") `
    -Destination $SitePackages -Recurse

$PathConfiguration = @(
    "python312.zip",
    ".",
    "Lib\site-packages",
    "..\backend",
    "import site"
) -join [Environment]::NewLine
[System.IO.File]::WriteAllText(
    (Join-Path $PythonTarget "python312._pth"),
    $PathConfiguration + [Environment]::NewLine
)

Copy-Item -Path (Join-Path $ProjectRoot "backend\*") `
    -Destination (Join-Path $PayloadRoot "backend") -Recurse
Copy-Item -Path (Join-Path $CcxDirectory "*.ccx") `
    -Destination (Join-Path $PayloadRoot "plugin")

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    $PayloadRoot,
    $PayloadArchive,
    [System.IO.Compression.CompressionLevel]::Optimal,
    $false
)

$CompressionAssembly = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\System.IO.Compression.dll"
$CompressionFileSystemAssembly = `
    "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\System.IO.Compression.FileSystem.dll"
$WindowsFormsAssembly = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\System.Windows.Forms.dll"
$LauncherSource = Join-Path $ProjectRoot "launcher\Program.cs"

& $Compiler `
    /nologo `
    /target:winexe `
    /platform:x64 `
    /optimize+ `
    "/win32icon:$IconFile" `
    "/reference:$CompressionAssembly" `
    "/reference:$CompressionFileSystemAssembly" `
    "/reference:$WindowsFormsAssembly" `
    "/resource:$PayloadArchive,CaptionGuardPayload" `
    "/out:$OutputFile" `
    $LauncherSource
if ($LASTEXITCODE -ne 0) {
    throw "Failed to compile CaptionGuard-CN.exe."
}

Write-Host "Built: $OutputFile"
