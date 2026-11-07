# Called by the per-user scheduled task after Windows sign-in.
$ErrorActionPreference = 'Stop'
Start-Sleep -Seconds 45
$script = Join-Path $PSScriptRoot 'start-remote.ps1'
& $script
