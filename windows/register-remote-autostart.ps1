# Run after one successful interactive Start-ViePN-Remote.bat setup.
# Registers for the current Windows user only; does not need admin rights.
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Launcher = Join-Path $Root 'Start-ViePN.bat'
$TaskName = 'ViePN iOS Manager - Private Remote Control'
$User = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$Exe = Join-Path $env:SystemRoot 'System32\cmd.exe'
$Arguments = '/c ""' + $Launcher + '" --auto"'
$Action = New-ScheduledTaskAction -Execute $Exe -WorkingDirectory $Root -Argument $Arguments
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $User
$Principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Description 'Launch ViePN local backend and private Tailscale HTTPS gateway after user logon' -Force | Out-Null
Write-Host 'ViePN private remote autostart was enabled for this Windows user.' -ForegroundColor Green
Write-Host 'The single Start-ViePN.bat launches after Windows sign-in.'
