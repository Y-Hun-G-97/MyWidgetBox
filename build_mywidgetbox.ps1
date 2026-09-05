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
Start-Sleep -Milliseconds 300

$targetDist = Join-Path $root "dist\MyWidgetBox"
if (Test-Path -LiteralPath $targetDist) {
    try {
        Remove-Item -LiteralPath $targetDist -Recurse -Force -ErrorAction Stop
    } catch {
        $tempTrash = Join-Path $root ("dist\trash_" + [Guid]::NewGuid().ToString("N"))
        try {
            Rename-Item -LiteralPath $targetDist -NewName (Split-Path -Leaf $tempTrash) -Force
            Remove-Item -LiteralPath $tempTrash -Recurse -Force -ErrorAction SilentlyContinue
        } catch {}
    }
}

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
$distMyWidgetBoxIcoPath = Join-Path $root "dist\MyWidgetBox\MyWidgetBox.ico"
Copy-Item -LiteralPath $iconSourcePath -Destination $distIconPath -Force
Copy-Item -LiteralPath $iconSourcePath -Destination $distMyWidgetBoxIcoPath -Force
Write-Host "[build] copied icon sidecars: $distIconPath and $distMyWidgetBoxIcoPath"

$assetsSourcePath = Join-Path $root "assets"
$distAssetsPath = Join-Path $root "dist\MyWidgetBox\assets"
if (Test-Path -LiteralPath $assetsSourcePath) {
    Copy-Item -LiteralPath $assetsSourcePath -Destination $distAssetsPath -Recurse -Force
    Write-Host "[build] copied assets: $distAssetsPath"
}

$guideTxtSource = Join-Path $root "README.txt"
$distGuideTxt = Join-Path $root "dist\MyWidgetBox\README.txt"
if (Test-Path -LiteralPath $guideTxtSource) {
    Copy-Item -LiteralPath $guideTxtSource -Destination $distGuideTxt -Force
    Write-Host "[build] copied guide text: $distGuideTxt"
}

Write-Host "[build] creating distribution zip package..."
$zipPath = Join-Path $root "dist\MyWidgetBox_v6.0.zip"
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $targetDist "*") -DestinationPath $zipPath -Force
Write-Host "[build] created release zip: $zipPath"

Write-Host "[build] done: $exePath"
