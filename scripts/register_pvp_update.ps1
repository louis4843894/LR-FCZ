param([switch]$Inspect)
$ErrorActionPreference = 'Stop'
$taskName = 'LR-Local-PVP-Auto-10min'
if ($Inspect) {
    Get-ScheduledTask -TaskName $taskName | Select-Object TaskName,State
    Get-ScheduledTaskInfo -TaskName $taskName | Select-Object NextRunTime,LastRunTime,LastTaskResult
    exit
}
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonPath = (Get-Command python -ErrorAction Stop).Source
$pythonwPath = Join-Path (Split-Path $pythonPath) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonwPath)) { throw 'Existing Python GUI launcher missing; do not start a visible background console.' }
$worker = Join-Path $projectRoot 'scripts\pvp_auto_update.py'
$arguments = '"' + $worker + '"'
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    if ($existing.Actions.Execute -ne $pythonwPath -or $existing.Actions.Arguments -ne $arguments -or $existing.Actions.WorkingDirectory -ne $projectRoot) { throw 'Existing PVP task differs; refusing to overwrite it.' }
    if ($existing.Settings.ExecutionTimeLimit -ne 'PT45M') {
        $existing.Settings.ExecutionTimeLimit = 'PT45M'
        Set-ScheduledTask -TaskName $taskName -Settings $existing.Settings | Out-Null
    }
} else {
    $action = New-ScheduledTaskAction -Execute $pythonwPath -Argument $arguments -WorkingDirectory $projectRoot
    $trigger = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1)) -RepetitionInterval (New-TimeSpan -Minutes 10)
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 45) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    $principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'LR ranked PVP Gold and above, all native 1/2/3 subdivisions; normal authorized local session only. Cache/lock, no login, pause on denial/rate limit, preserve versions.' | Out-Null
}
& $pythonPath $worker --enable
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName,State
