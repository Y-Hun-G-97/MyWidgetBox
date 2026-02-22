param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Test-FileOrThrow {
    param([string]$PathValue, [string]$Label)
    if (-not (Test-Path -LiteralPath $PathValue -PathType Leaf)) {
        throw "$Label not found: $PathValue"
    }
}

Write-Host "[build] start"

Test-FileOrThrow -PathValue ".\MyCanvas.spec" -Label "Spec"
Test-FileOrThrow -PathValue ".\MyCanvas.py" -Label "Main script"
Test-FileOrThrow -PathValue ".\MyCanvas.ico" -Label "Icon"
Test-FileOrThrow -PathValue "C:\ffmpeg\bin\ffmpeg.exe" -Label "ffmpeg"
Test-FileOrThrow -PathValue "C:\ffmpeg\bin\ffprobe.exe" -Label "ffprobe"

python -m PyInstaller --noconfirm --clean .\MyCanvas.spec

$exePath = Join-Path $root "dist\MyCanvas.exe"
if (-not (Test-Path -LiteralPath $exePath -PathType Leaf)) {
    throw "Build output missing: $exePath"
}

$iconSourcePath = Join-Path $root "MyCanvas.ico"
$distIconPath = Join-Path $root "dist\icon.ico"
Copy-Item -LiteralPath $iconSourcePath -Destination $distIconPath -Force
Write-Host "[build] copied icon sidecar: $distIconPath"

Write-Host "[build] done: $exePath"
