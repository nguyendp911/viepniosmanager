# Register an interactive-user background server on Windows logon.
# ViePN's server scans signatures every 30 minutes and re-signs before expiry.
# PC must stay powered on. iPhone must be reachable by USB or supported Wi-Fi.
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Script = Join-Path $Root 'windows\start.ps1'
if (-not (Test-Path (Join-Path $Root '.venv\Scripts\python.exe'))) {
    throw 'Install ViePN first: windows\setup.ps1'
}
$TaskName = 'ViePN iOS Manager - Auto Renew'
$User = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$Exe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$Action = New-ScheduledTaskAction -Execute $Exe -WorkingDirectory $Root -Argument ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $Script + '"')
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $User
$Principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Description 'ViePN checks and refreshes expiring personal iOS app profiles before 7 days.' -Force | Out-Null
Write-Host ('Registered ' + $TaskName) -ForegroundColor Green
Write-Host 'It starts when this Windows user signs in. The phone must be reachable.'
Write-Host 'If the dashboard is already running, the new task will not take port 8765.'
