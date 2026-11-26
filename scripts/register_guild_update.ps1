param([switch]$Inspect)
$ErrorActionPreference = 'Stop'
$taskName = 'LR-Local-Guild-Tuesday-Noon'
if ($Inspect) {
    Get-ScheduledTask -TaskName $taskName | Select-Object TaskName,State
    Get-ScheduledTaskInfo -TaskName $taskName | Select-Object NextRunTime,LastRunTime,LastTaskResult
    exit
}
# Scheduled Tasks uses the Windows local time zone. Never change the user's zone.
if ((Get-TimeZone).BaseUtcOffset.TotalMinutes -ne 480 -or (Get-TimeZone).SupportsDaylightSavingTime) {
    throw 'Windows time zone must be UTC+8 without daylight saving for the Asia/Taipei trigger.'
}
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonPath = (Get-Command python -ErrorAction Stop).Source
$scriptPath = Join-Path $projectRoot 'scripts\update_local_game_data.py'
$legacyArguments = '"' + $scriptPath + '" --module guild --capture --if-due'
$normalArguments = $legacyArguments + ' --use-authorized-runtime-session --sync-supabase'
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument $normalArguments -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Tuesday -At '12:00'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 15) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'LR guild-war ranks 1-100 and visible rosters: Tuesday noon Asia/Taipei. Uses only an authorized in-memory game session, preserves prior data, saves a private Supabase draft. No team edits or publishing.'
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    # Preserve unrelated existing tasks; do not replace a task pointing elsewhere.
    if ($existing.Actions.Execute -ne $pythonPath -or $existing.Actions.WorkingDirectory -ne $projectRoot -or $existing.Actions.Arguments -notin @($legacyArguments,$normalArguments)) { throw 'Existing task differs; refusing to overwrite it.' }
    if ($existing.Actions.Arguments -eq $legacyArguments) {
        # Update only this task's known legacy action; preserve user trigger,
        # principal, enabled/disabled state and other task settings.
        Set-ScheduledTask -TaskName $taskName -Action $action | Out-Null
    }
} else { Register-ScheduledTask -TaskName $taskName -InputObject $task | Out-Null }
Get-ScheduledTaskInfo -TaskName $taskName | Select-Object NextRunTime,LastRunTime,LastTaskResult
