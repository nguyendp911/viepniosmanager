# ViePN private remote control via Tailscale Serve, Windows PowerShell 5.1.
# ASCII-only script avoids encoding problems. NO OPEN ROUTER PORTS REQUIRED.
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root
$LocalPort = if ($env:VIEPN_PORT) { [int]$env:VIEPN_PORT } else { 8765 }
$GatewayPort = if ($env:VIEPN_REMOTE_PORT) { [int]$env:VIEPN_REMOTE_PORT } else { 8766 }

if ($LocalPort -eq $GatewayPort) {
    throw 'Main API and remote gateway must have different ports.'
}
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    throw 'Python environment missing; run windows\setup.ps1 first.'
}

function Test-Health([int]$Port) {
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
        return ($r.ok -eq $true)
    } catch {
        return $false
    }
}
function Assert-LoopbackOnly([int]$Port) {
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
    foreach ($entry in $listeners) {
        if ($entry.LocalAddress -notin @('127.0.0.1','::1')) {
            throw "PORT $Port LISTENS ON $($entry.LocalAddress). Stop your old server bound to 0.0.0.0 before enabling remote access."
        }
    }
}
function Start-Window([string]$Script) {
    $scriptFile = Join-Path $Root ('windows\' + $Script)
    Start-Process -FilePath 'powershell.exe' -WorkingDirectory $Root -ArgumentList @(
        '-NoProfile','-ExecutionPolicy','Bypass','-NoExit',
        '-File', ('"' + $scriptFile + '"')
    ) | Out-Null
}
function Wait-Health([int]$Port) {
    for ($i = 0; $i -lt 25; $i++) {
        if (Test-Health $Port) { return }
        Start-Sleep -Milliseconds 500
    }
    throw "Port $Port did not become healthy. Read its PowerShell window."
}

Assert-LoopbackOnly $LocalPort
if (-not (Test-Health $LocalPort)) {
    Write-Host 'Starting ViePN local API...' -ForegroundColor Cyan
    Start-Window 'start-local-for-remote.ps1'
    Wait-Health $LocalPort
}
Assert-LoopbackOnly $LocalPort

Assert-LoopbackOnly $GatewayPort
if (-not (Test-Health $GatewayPort)) {
    Write-Host 'Starting restricted remote gateway...' -ForegroundColor Cyan
    Start-Window 'start-remote-gateway.ps1'
    Wait-Health $GatewayPort
}
Assert-LoopbackOnly $GatewayPort

$Tailscale = (Get-Command tailscale.exe -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Source)
if (-not $Tailscale) {
    $candidate = Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe'
    if (Test-Path -LiteralPath $candidate) { $Tailscale = $candidate }
}
if (-not $Tailscale) {
    Write-Host 'Please install Tailscale for Windows: https://tailscale.com/download/windows' -ForegroundColor Yellow
    throw 'Tailscale executable not found. Backend and gateway are running locally.'
}
$statusText = (& $Tailscale status --json 2>$null | Out-String)
if ($LASTEXITCODE -ne 0) {
    throw 'Tailscale is not connected. Sign in using the Tailscale Windows app first.'
}
$status = $statusText | ConvertFrom-Json
if ($status.BackendState -ne 'Running') {
    throw 'Tailscale is not running. Sign in and enable Tailscale on Windows.'
}
$dns = [string]$status.Self.DNSName
if (-not $dns) { throw 'Tailscale MagicDNS name not found; enable MagicDNS and HTTPS certificates in your tailnet.' }

# Only Tailscale Serve. NEVER Funnel: Funnel publishes to the whole Internet.
Write-Host 'Enabling private HTTPS reverse proxy inside YOUR tailnet...' -ForegroundColor Cyan
& $Tailscale serve --bg --https=443 "http://127.0.0.1:$GatewayPort"
if ($LASTEXITCODE -ne 0) {
    throw 'Tailscale Serve failed. Follow the printed prompt to enable tailnet HTTPS, then re-run.'
}
& $Tailscale serve status

$url = 'https://' + $dns.TrimEnd('.')
Write-Host ''
Write-Host 'ViePN remote-control URL:' -ForegroundColor Green
Write-Host $url -ForegroundColor Green
Write-Host 'Enter this URL and your ViePN dashboard token in the iPhone app.'
Write-Host 'Both devices must be signed into the SAME Tailscale tailnet.'
Write-Host 'Apple ID password/2FA/session controls are NOT exposed by this gateway.'
