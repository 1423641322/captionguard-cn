$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonDirectory = Join-Path $ProjectRoot ".build-python312"
$Python = Join-Path $PythonDirectory "python.exe"
$PythonVersion = "3.12.10"
$ArchiveName = "python-$PythonVersion-embed-amd64.zip"
$ArchiveUrl = "https://www.python.org/ftp/python/$PythonVersion/$ArchiveName"
$GetPipUrl = "https://bootstrap.pypa.io/get-pip.py"
$env:PYTHONNOUSERSITE = "1"

if (Test-Path -LiteralPath $Python) {
    & $Python -m pip --version 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Output $Python
        exit 0
    }
}

New-Item -ItemType Directory -Force -Path $PythonDirectory | Out-Null
$ArchivePath = Join-Path $PythonDirectory $ArchiveName
$GetPipPath = Join-Path $PythonDirectory "get-pip.py"

if (-not (Test-Path -LiteralPath $Python)) {
    Invoke-WebRequest -Uri $ArchiveUrl -OutFile $ArchivePath
    Expand-Archive -LiteralPath $ArchivePath -DestinationPath $PythonDirectory -Force
}

$PathFile = Join-Path $PythonDirectory "python312._pth"
$PathContents = [System.IO.File]::ReadAllText($PathFile).Replace("#import site", "import site")
[System.IO.File]::WriteAllText($PathFile, $PathContents)

for ($Attempt = 1; $Attempt -le 3; $Attempt++) {
    try {
        Invoke-WebRequest -Uri $GetPipUrl -OutFile $GetPipPath
        break
    }
    catch {
        if ($Attempt -eq 3) {
            throw
        }
    }
}
& $Python $GetPipPath --disable-pip-version-check
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install pip in the Python 3.12 build environment."
}

Write-Output $Python
