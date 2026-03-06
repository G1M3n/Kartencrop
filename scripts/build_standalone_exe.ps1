param(
    [switch]$Clean,
    [string]$DistPath = "dist_portable",
    [string]$WorkPath = "build_portable"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$specFile = Join-Path $projectRoot "kartencrop_ui.spec"

if (-not (Test-Path $pythonExe)) {
    throw "Python im venv nicht gefunden: $pythonExe"
}

function Resolve-BuildPath {
    param(
        [string]$BasePath,
        [string]$AppDirectory
    )

    $targetPath = Join-Path $projectRoot $BasePath
    $appPath = Join-Path $targetPath $AppDirectory

    if (-not (Test-Path $appPath)) {
        return $BasePath
    }

    try {
        Remove-Item -Path $appPath -Recurse -Force -ErrorAction Stop
        return $BasePath
    }
    catch {
        $suffix = Get-Date -Format "yyyyMMdd_HHmmss"
        return "${BasePath}_$suffix"
    }
}

$DistPath = Resolve-BuildPath -BasePath $DistPath -AppDirectory "KartencropUI"

$arguments = @("-m", "PyInstaller", "--noconfirm")
if ($Clean) {
    $arguments += "--clean"
}
$arguments += @("--distpath", $DistPath, "--workpath", $WorkPath)
$arguments += $specFile

Push-Location $projectRoot
try {
    & $pythonExe @arguments
    Write-Host "Build-Ausgabe: $DistPath\\KartencropUI"
}
finally {
    Pop-Location
}
