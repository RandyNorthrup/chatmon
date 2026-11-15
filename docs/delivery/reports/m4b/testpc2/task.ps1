param([ValidateSet('run', 'remove')][string]$Mode = 'run', [int]$TimeoutMinutes = 9)
# testpc2, over ssh as Technician: run W:\chatmon-m4b\rec\run.ps1 in Technician's signed-in console session, where
# toasts are shown (ssh's own logon is not interactive), through an on-demand scheduled task with no trigger, and
# wait for it. `remove` unregisters the task.
$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -ne 'TESTPC2') { throw "not TESTPC2: $env:COMPUTERNAME" }
$name = 'ChatmonM4BToastDrill'
$logs = 'W:\chatmon-m4b\logs'
if ($Mode -eq 'remove') {
    Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
    "task $name registered after removal: $([bool](Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue))"
    exit 0
}
"== $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz'))"
query user 2>&1
$console = (query user 2>&1 | Select-String '^\s*>?technician\s+console\s+(\d+)\s+Active')
if (-not $console) { throw "Technician is not signed in and active at the console" }
if (Test-Path "$logs\done.txt") { throw "a run already finished here: $logs\done.txt" }
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File W:\chatmon-m4b\rec\run.ps1'
$principal = New-ScheduledTaskPrincipal -UserId "$env:COMPUTERNAME\Technician" -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 40) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $name -Action $action -Principal $principal -Settings $settings -Description 'Chatmon M4B toast drill (AC-03E), on demand; removed after' | Out-Null
$task = Get-ScheduledTask -TaskName $name
"registered $name : user $($task.Principal.UserId), logon $($task.Principal.LogonType), run level $($task.Principal.RunLevel), triggers $(@($task.Triggers).Count)"
Start-ScheduledTask -TaskName $name
"started $((Get-Date).ToString('HH:mm:ss'))"
$deadline = (Get-Date).AddMinutes($TimeoutMinutes)
while (-not (Test-Path "$logs\done.txt") -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 5 }
Start-Sleep -Seconds 2
$info = Get-ScheduledTaskInfo -TaskName $name
"finished: $(Test-Path "$logs\done.txt"); task state $((Get-ScheduledTask -TaskName $name).State), last run $($info.LastRunTime), last result $($info.LastTaskResult)"
if (Test-Path "$logs\run.log") { Get-Content "$logs\run.log" }
