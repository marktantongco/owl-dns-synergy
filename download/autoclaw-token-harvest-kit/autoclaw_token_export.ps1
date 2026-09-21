# AutoClaw desktop-token harvester (Windows quick path)
# Locates the AutoClaw Local Storage leveldb, copies it to %TEMP%, and
# invokes the Python parser. Safe: read-only on app data, no network.

$ErrorActionPreference = "Stop"

$roots = @(
    "$env:LOCALAPPDATA\AutoClaw",
    "$env:APPDATA\AutoClaw",
    "$env:LOCALAPPDATA\autoclaw",
    "$env:APPDATA\autoclaw",
    "$env:LOCALAPPDATA\Programs\AutoClaw"
) | Where-Object { Test-Path $_ }

if (-not $roots) {
    Write-Host "AutoClaw data directory not found under LOCALAPPDATA/APPDATA."
    Write-Host "Log into the AutoClaw desktop app once, then re-run."
    exit 1
}

$leveldb = Get-ChildItem -Path $roots -Recurse -Directory -Filter "leveldb" |
    Where-Object { $_.FullName -match "Local Storage" } |
    Select-Object -First 1

if (-not $leveldb) {
    Write-Host "leveldb under 'Local Storage' not found; roots searched:"
    $roots | ForEach-Object { Write-Host "  $_" }
    exit 1
}

Write-Host "found: $($leveldb.FullName)"
$tmp = Join-Path $env:TEMP ("aclaw-ls-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory -Path $tmp | Out-Null
Copy-Item -Path (Join-Path $leveldb.FullName "*") -Destination $tmp -Force

$py = (Get-Command python -ErrorAction SilentlyContinue) ?? (Get-Command py -ErrorAction SilentlyContinue)
$script = Join-Path $PSScriptRoot "harvest_token.py"
if ($py -and (Test-Path $script)) {
    & $py.Source $script $tmp --out (Join-Path (Get-Location) "autoclaw_token.json")
} else {
    Write-Host "python or harvest_token.py not available; leveldb copied to:"
    Write-Host "  $tmp"
    Write-Host "Run on any machine with Python:  python harvest_token.py `"$tmp`""
}
