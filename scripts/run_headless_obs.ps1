param(
    [int]$Port = 8765,
    [switch]$DesktopAudio
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $repo "data"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Start-Transcript -Path (Join-Path $logDir "headless-obs.log") -Append | Out-Null
$python = Join-Path $env:USERPROFILE "anaconda3\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
}

Set-Location -LiteralPath $repo
$arguments = @(
    "main.py",
    "--headless",
    "--continuous-play",
    "--allow-multiple",
    "--overlay-port",
    "$Port"
)
if (-not $DesktopAudio) {
    $arguments += "--mute"
}

try {
    & $python @arguments
} finally {
    Stop-Transcript | Out-Null
}
