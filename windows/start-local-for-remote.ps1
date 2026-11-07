# Keep the main ViePN service on localhost only.
$ErrorActionPreference = 'Stop'
$env:VIEPN_HOST = '127.0.0.1'
$Root = Split-Path -Parent $PSScriptRoot
& (Join-Path $Root 'windows\start.ps1')
