param(
    [string]$PythonPath = (Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe')
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $PythonPath)) { throw 'Install requirements in .venv first, or pass -PythonPath.' }
$scriptPath = Join-Path $PSScriptRoot 'session_task.py'
$action = New-ScheduledTaskAction -Execute $PythonPath -Argument ('"' + $scriptPath + '"') -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 4) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'DealerStudio-Session-Renewal' -Description 'Validate and renew the configured Dealer Studio session every five minutes while this user is signed in.' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Select-Object TaskName,State
