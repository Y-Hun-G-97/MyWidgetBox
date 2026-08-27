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

Test-FileOrThrow -PathValue ".\MyWidgetBox.spec" -Label "Spec"
Test-FileOrThrow -PathValue ".\MyWidgetBox.py" -Label "Main script"
Test-FileOrThrow -PathValue ".\MyWidgetBox.ico" -Label "Icon"
Test-FileOrThrow -PathValue "C:\ffmpeg\bin\ffmpeg.exe" -Label "ffmpeg"
Test-FileOrThrow -PathValue "C:\ffmpeg\bin\ffprobe.exe" -Label "ffprobe"

Get-Process -Name "MyWidgetBox" -ErrorAction SilentlyContinue | ForEach-Object {
    try { $_.CloseMainWindow() | Out-Null } catch {}
}
Start-Sleep -Milliseconds 450
Get-Process -Name "MyWidgetBox" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

$pyExecutable = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    try {
        & py -3.14 -m PyInstaller --version | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $pyExecutable = "py -3.14"
        }
    } catch {}
}
if (-not $pyExecutable) {
    $pyExecutable = "python"
}

if ($pyExecutable -eq "py -3.14") {
    py -3.14 -m PyInstaller --noconfirm --clean .\MyWidgetBox.spec
} else {
    python -m PyInstaller --noconfirm --clean .\MyWidgetBox.spec
}
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$exePath = Join-Path $root "dist\MyWidgetBox\MyWidgetBox.exe"
if (-not (Test-Path -LiteralPath $exePath -PathType Leaf)) {
    throw "Build output missing: $exePath"
}

$iconSourcePath = Join-Path $root "MyWidgetBox.ico"
$distIconPath = Join-Path $root "dist\MyWidgetBox\icon.ico"
Copy-Item -LiteralPath $iconSourcePath -Destination $distIconPath -Force
Write-Host "[build] copied icon sidecar: $distIconPath"

Write-Host "[build] done: $exePath"
