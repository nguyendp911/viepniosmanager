# Disable private HTTPS Serve. Does not delete tokens or any IPA files.
$ErrorActionPreference = 'Stop'
$cli = (Get-Command tailscale.exe -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Source)
if (-not $cli) {
    $cli = Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe'
}
if (-not (Test-Path -LiteralPath $cli)) { throw 'Tailscale not installed.' }
& $cli serve --https=443 off
if ($LASTEXITCODE -ne 0) { throw 'Cannot disable Tailscale Serve; check its status.' }
Write-Host 'ViePN private Tailscale Serve is now disabled.' -ForegroundColor Green
